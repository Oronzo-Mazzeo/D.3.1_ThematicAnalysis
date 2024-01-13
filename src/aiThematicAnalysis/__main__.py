#! /usr/bin/env python3
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PosixPath
from time import sleep
import json

import pandas as pd
import rich_click as click
import yaml
from rich import inspect
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.status import Status
from striprtf.striprtf import rtf_to_text

console = Console()
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])

progrSet = [
    SpinnerColumn(finished_text=":thumbs_up-emoji:"),
    "[progress.description]{task.description}",
    BarColumn(finished_style="green"),
    "[progress.percentage]{task.percentage:>3.0f}%",
    "{task.completed:>6d} of {task.total:6d}",
    TimeElapsedColumn(),
]
output = Path("response.md")


class MSG:
    ERROR = "[red][ERROR][/red] "
    INFO = "[blue][INFO][/blue] "
    WARNING = "[yellow][WARNING][/yellow] "

class Configure:
    def __init__(self):
        self.legacy=False
        keyFile=Path("~/.themAnalysis.yml").expanduser()
        if not keyFile.exists():
            console.print(f"{MSG.WARNING}The API Key file not exists")
            api=Prompt.ask("Please insert the ChatGPT API Key", console=console)
            data={'api_key':api}
            with open(keyFile,'w') as fl:
                yaml.dump(data,fl)
            self.api_key=api
        else:
            with open(keyFile,'r') as fl:
                data = yaml.load(fl,Loader=yaml.FullLoader)
            self.api_key=data['api_key']
        
                
    
configure=Configure()


def reader():
    with open('questions.yml') as f:
        dat = yaml.safe_load(f)
    return dat


questions = reader()
    
@dataclass
class AI:
    BARD='bard'
    CHATGPT="chatgpt"


    
@dataclass
class FOLDER:
    CHUNK=Path("chunk")
    
def create_folders()->None:
    for item in [FOLDER.CHUNK]:
        if not item.exists():
            item.mkdir(parents=True)
    return None

def catch_strings(input_string: str) -> list:
    pattern = r'"([^"]*)"'
    matches = re.findall(pattern, input_string)
    return matches

def test(elem):
    if type(elem) is str:
        return elem.lower()
    else:
        return elem
    
def trova_indici_uguali(lista, stringa):
    return [i for i, elemento in enumerate(lista) if test(elemento) == stringa]


def builder(input: str,tp:str='ph2_2') -> dict:
    blocks = catch_strings(input.replace('”','"'))
    if tp=='ph2_2':
        elems = ["name", "description", "quote"]
    elif tp=='ph3':
        elems=['group','topic','description']

    return {
        item: [blocks[i + 1] for i in trova_indici_uguali(blocks, item)]
        for item in elems
    }


def topic_list(text: str) -> list:
    blocks = catch_strings(text)
    topic_idx = trova_indici_uguali(blocks, 'topics')
    index_idx = trova_indici_uguali(blocks, 'indices')
    myList = []
    for idx, item in enumerate(topic_idx):
        myList.extend(blocks[item+1:index_idx[idx]])
    return myList


# lang = {'it': 'italian',
#         'en': 'english'}

# questions = {'en':{
#     'main': """    Identify up to 3 most relevant themes in the following text, provide a name for each theme in no more than 3 words, 4 lines meaningful and dense description of the theme and a quote from the respondent for each theme non longer tha 7 lines.
# Format the response as json file keeping names, descriptions and quotes together in the json, anche keep them together in 'Themes'.
# """
# }}


def chat(question: str):
    # Effettua una richiesta a ChatGPT
    import openai
    openai.api_key = configure.api_key
    if configure.legacy:
        engine = "text-davinci-002"
    else:
        engine = "gpt-3.5-turbo-instruct"
    try:
        response = openai.completions.create(
        model=engine,  # Specifica il motore di generazione
        prompt=question,
        max_tokens=1000,  # Specifica il numero massimo di token per la risposta
    )
    except Exception as e:
        print(e)
        exit()

    return response

    

def question_builder(
    language: str, question: str, num:str=None, chunck: str = None, topics: list = None, ai:str=AI.CHATGPT
):
    # if language == 'it':
    #     console.print(f"{MSG.ERROR}Language not implemented")
    #     close_prog(1)
    newChunck = f"```{chunck}```"
    text = f"""
    {questions['questions'][language][question]}
    {newChunck if chunck is not None else ''}
    """
    if topics is not None:
        text += f"""\n List of topics: {",".join(topics)}\n"""
    with open(output,'a') as fl:
        fl.write(f"\n# Question {num}:\n\n{text}\n\n")
    if ai==AI.CHATGPT:
        ret = chat(text)
    elif ai==AI.BARD:
        pass
    return ret


def readDF(prefix):
    import pandas as pd

    data = pd.DataFrame(columns=["FileName", "Chunk", "Tokens"])

    files = FOLDER.CHUNK.glob(f"{prefix}*.txt")
    # print(files)
    for item in files:
        with open(item, "r") as fl:
            text = fl.read()
        ln = [item, text, len(text.split(" "))]
        data.loc[len(data)] = ln
    return data


def divide_file(file_path, chunk_size, prefix):
    if type(file_path) is PosixPath:
        with open(file_path, "r") as file:
            lines = file.readlines()
        content = " ".join([x.strip() for x in lines])
    else:
        content = file_path
    content = content.split(" ")
    chunks = [content[i: i + chunk_size]
              for i in range(0, len(content), chunk_size)]

    for i, chunk in enumerate(chunks):
        with open(FOLDER.CHUNK.joinpath(f"{prefix}_{i:03}.txt"), "w") as chunk_file:
            chunk_file.write(" ".join(chunk))


def num_replace(content, language):
    from re import sub

    from num2words import num2words

    def myreplace(match):
        match = match.group()
        # patch to fix an error in the num2words
        # if match.isdigit():
        #     digit = int(match)
        # else:
        #     digit = float(match)

        # num = num2words(digit, lang=language)

        # return f" {num}"
        # end of patch
        return f" {num2words(match,lang=language)}"

    content = sub(r"\d+", myreplace, content)
    return content


def rem_punctuation(content):
    from string import punctuation

    content = content.translate(str.maketrans("", "", punctuation))
    # Removing special symbols not in string.punctuation
    content = content.translate(
        str.maketrans({"”": "", "’": " ", "–": "", "“": "", "…": ""})
    )
    return content


def rem_stop_words(content, language):
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize

    try:
        tokens = word_tokenize(content)
    except:
        from nltk import download

        download("punkt")
        download("stopwords")
        tokens = word_tokenize(content)
    stop_words = set(stopwords.words(language))
    results = [i for i in tokens if not i in stop_words]
    content = " ".join(results)
    return content


def close_prog(status):
    console.rule(style="green")
    console.print(
        "Ending Thematic Analizer", style="bold red on yellow", justify="center"
    )
    console.rule(style="green")
    from shutil import rmtree
    rmtree(FOLDER.CHUNK)
    # elem = Path().glob("chunck*.txt")
    # for item in elem:
    #     item.unlink()
    sys.exit(status)


@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument("filename", type=click.Path(), default=None, required=False)
@click.option("-f", "--folder", metavar="FOLDER", help="Get all the interview in the folder", default=None,)
@click.option("-c","--csv",metavar="FILE",help="Start the analysis from the list of topics in CSV format", default=None, type=click.Path())
@click.option("-o", "--output", "outfile", type=str, help="Output filename", default="output.txt", show_default=True,)
@click.option("-a", "--ai", type=click.Choice(["ChatGPT", "Bard"], case_sensitive=False), help="select the AI to use", default="ChatGPT", show_default=True,)
@click.option("-w", "--wait-time", "slTime", type=int, help="Number of seconds between the requests", default=20,show_default=True)
@click.option("-l", "--language", type=click.Choice(questions["language"].keys(), case_sensitive=True),  help="Select the language to use", default="en", show_default=True,)
@click.option("--split/--no-split", default=True, help="Enable the file splitting", show_default=True,)
@click.option("--stopw/--no-stopw",  default=True, help="Enable the stop word remove", show_default=True,)
@click.option("-n", "--n-words", type=int, metavar="NLINES", help="number of words in parts", default=2000, show_default=True,)
@click.option("-p", "--prefix", type=str, help="Prefix of the file", default="chunk", show_default=True,)
@click.option("-L", "--legacy", "legacyFlag", is_flag=True, help="Enable the engine text-davinci-002 insted of gpt-3.5-turbo-instruct", default=False,)
def action(filename: Path, folder: str,csv:Path, outfile: str, ai: str, slTime: int, language: str, split: bool, stopw: bool, n_words: int, prefix: str, legacyFlag: bool,):
    ai=ai.lower()
    csvFlag=False
    # chat_gemini2()
    create_folders()
    console.rule(style="green")
    console.print(
        "Starting Thematic Analizer", style="bold red on yellow", justify="center"
    )
    console.rule(style="green")
    configure.legacy = legacyFlag
    
    if ai == AI.BARD:
      console.print(f"{MSG.WARNING}Bard is only partially supported. Switching to ChatGPT")
      ai= AI.CHATGPT  
    
    if not filename is None:
        filename = Path(filename)
        if not filename.exists():
            console.print(f"{MSG.ERROR}The file {filename.name} not exists")
            sys.exit(1)
        if filename.suffix == ".txt":
            with open(filename, "r") as file:
                lines = file.readlines()
        elif filename.suffix == ".rtf":
            # testare se è corretto l'rtf
            with open(filename, "r") as file:
                content = file.read()
                text = rtf_to_text(content)
                lines = text.split("\n")
    else:
        if folder is None:
            if csv is None:
                console.print(
                    f"{MSG.ERROR}A file, with the interview or with the topics, or a folder must be declared\n see help")
                sys.exit(1)
            else:
                csvFlag=True
        else:
            folder = Path(folder)
            fileList=[]
            extensions=['*.rtf','*.txt']
            for ext in extensions:
                fileList.extend(folder.glob(ext))
            if len(fileList) == 0:
                console.print(f"{MSG.ERROR}No file found i the folder {folder.name}")
            lines = []
            for item in fileList:
                with open(item, "r",encoding='latin-1') as file:
                    content = file.read()
                    text = rtf_to_text(content)
                    tempLines = text.split("\n")
                    lines = [*lines, *tempLines]
    if not csvFlag:
        content = " ".join([x.strip() for x in lines])
        
        if output.exists():
            output.unlink()

        #   TEXT PREPROCESSIG =====================> BEGIN

        # CONVERTING ALL LETTERS TO LOWER CASE
        console.print(
            f":white_heavy_check_mark: Converting all letters to lower case")
        content = content.lower()

        # CONVERTING NUMBERS INTO WORDS OR REMVING NUMBERS
        with Status(
            "Converting numbers into words or remving them",
            spinner="aesthetic",
            console=console,
        ) as status:
            content = num_replace(content, language)
        console.print(
            f":white_heavy_check_mark: Converting numbers into words or remving them"
        )

        # REMOVING PUCTUATIONS
        with Status("Removing puctuations", spinner="aesthetic", console=console) as status:
            content = rem_punctuation(content)
        console.print(f":white_heavy_check_mark: Removing puctuations")

        # REMOVING WHITESPACES
        content = content.strip()
        console.print(f":white_heavy_check_mark: Removing whitespaces")

        # REMOVING STOP WORDS
        if stopw:
            with Status(
                "Removing stop words", spinner="aesthetic", console=console
            ) as status:
                content = rem_stop_words(content, questions["language"][language])
            console.print(f":white_heavy_check_mark: Removing stop words")
        else:
            console.print(f":cross_mark: Skipped removing stop words")

        #   TEXT PREPROCESSIG =====================> END

        # SPLIT FILE
        if split:
            with Status("Split File", spinner="aesthetic", console=console) as status:
                divide_file(content, n_words, prefix)
            console.print(f":white_heavy_check_mark: Split File")
        else:
            console.print(f":cross_mark: Split File")

        # Write the processed input file
        with open(outfile, "w") as file:
            file.write(content)

        with Status(
            "Analyzing data with AI", spinner="aesthetic", console=console
        ) as status:
            # Read data as dataframe
            data = readDF("chunk")

            data.to_csv("output.csv")
        a = 0
        with open(output, "a") as f:
            f.write("# Answar to Question **Ph2_1**\n\n")
        # Create an empty DataFrame
        df = pd.DataFrame()
        with Progress(*progrSet, console=console) as pr:
            taskCH = pr.add_task("Processing chunk", total=len(data["Chunk"]))
            for num,item in enumerate(data["Chunk"]):
                #
                ret = question_builder(language, "Ph2_1", num=num,chunck=item, ai=ai)
                # inspect(ret)
                with open(output, "a") as f:
                    f.write(f"\n## Request {num} \n\n{ret.choices[0].text}\n")
                    # f.write(ret.choices[0].text)
                pr.update(taskCH, advance=1)
                # returned_text = ret.choices[0].text

                returned_text = ret.choices[0].text
                # continue
                # if returned_text.startswith('{'):
                #     pass
                # else:
                #     returned_text="{"+returned_text+"{"
                df2 = pd.DataFrame.from_dict(
                    builder(returned_text), orient="index")
                df = pd.concat([df, df2.T])
                # Wait 20 seconds due to the free policy of chatGPT
                sleep(slTime)
        # exit()
        with Status("Saving The CSV file", spinner="aesthetic", console=console) as status:
            with open("results-ph2_1.csv", "w") as fl:
                df.to_csv(fl, index=False)
        console.print(f":white_heavy_check_mark: Save the CSV")
        if "warning" in vars(ret).keys():
            console.print(f"{MSG.WARNING}{ret.warning}")
        df=df.fillna('')
    else:
        df=pd.read_csv(csv).fillna('')
    with Status("Step Ph2_2", spinner="aesthetic", console=console) as status:
        ret2 = question_builder(language, "Ph2_2", num= "Ph2_2",topics=df["name"].to_list())

        with open(output, "a") as f:
            f.write(f"\n\n# Answer to Question Ph2_2 \n\n")
            f.write(ret2.choices[0].text)
        sleep(slTime)
    console.print(f":white_heavy_check_mark: Step Ph2_2")

    with Status("Step Ph3", spinner="aesthetic", console=console) as status:

        ret3 = question_builder(
            language, "Ph3", num="Ph3", topics=topic_list(ret2.choices[0].text)
        )

        with open(output, "a") as f:
            f.write(f"\n\n# Answer to Question Ph3 \n\n")
            f.write(ret3.choices[0].text)
        sleep(slTime)
        try:
            df2 = pd.json_normalize(json.loads(ret3.choices[0].text))
            for i, item in enumerate(df2["topic"]):
                alt=[]
                for elem in item:
                    tp=list(elem.keys())
                    # print(tp)
                    alt.append(f"{elem[tp[0]]} ({elem[tp[1]]})")
                
                df2["topics"][i]=', '.join(alt)
                
            # df2 = pd.DataFrame.from_dict(builder(ret3.choices[0].text,tp='ph3'),orient="index")
            with open("results-ph3.csv","w") as fl:
                df2.to_csv(fl,index=False)
            console.print(f":white_heavy_check_mark: Step Ph3")
        except:
            console.print(f":cross_mark: Error saving the CSV file.")
    

    with Status("Step Ph5", spinner="aesthetic", console=console) as status:
        ret5 = question_builder(language, "Ph5",num="Ph5",topics=topic_list(ret2.choices[0].text))
        with open(output, "a") as f:
            f.write(f"\n\n# Answer to Question Ph5 \n\n")
            f.write(ret5.choices[0].text)
    console.print(f":white_heavy_check_mark: Step Ph5")

    console.print(f":white_heavy_check_mark: Data Analized")

    close_prog(0)


if __name__ == "__main__":
    action()
