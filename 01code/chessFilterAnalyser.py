#setup

stockfish_path = "/usr/games/stockfish"


import chess.pgn
import chess
import chess.engine
import numpy as np
import pandas as pd
import io
import re
from itertools import count
engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)

#---------------------------

#How many games are in this file?

text_path =  "/home/ubuntu/chessProgram/wholeDatabase.txt"

games_text = open(text_path, mode = "r")
line_list = games_text.readlines()

EventTag = re.compile('.Event.')

game_count = 0

for line in line_list:
    if re.match(EventTag, line):
        game_count += 1
    

print("number of games = " + str(game_count))


# Creating list of all games

games_path =  "/home/ubuntu//chessProgram/wholeDatabase.pgn"

games = open(games_path)

game_list = []

game_iter = 0

for n in range(game_count*2):
    game_iter += 1
    game_list.append(chess.pgn.read_game(games))
    game_iter % 10000 == 0:
        print("progress: ", str(game_iter), "out of ", str(game_count*2))
        #Python is counting two games for each actual game for some reason:
        #one actual game that it can give information about, and just a series
        #of question marks. So I'm adding both (hence game_count*2) and then just deleting the
        #blank question mark games.

# Removing blank games

game_list = [game for game in game_list if '????.??.??' not in str(game)]

game_list = [game for game in game_list if game != None]


# Creating lists of information about each game, deleting games with incorrectly formatted headers

gameNum_list = []
year_list = []
w_elo_list = []
b_elo_list = []
outcome_list = []

for number, game in zip(count(len(game_list) - 1, -1), reversed(game_list)):
    gameNum_list.append(number + 1)
    try:
        year = re.match(r"\d{4}", game.headers["Date"])
        year_list.insert(0,int(year.group()))
    except AttributeError as error:
        del game_list[number]

    try:
        outcome_list.insert(0,str(game.headers["Result"]))
    except KeyError as error:
        del game_list[number]

# If a player's elo score isn't stored, it's replaced with a 0

    try:
        w_elo_list.insert(0, int(game.headers["WhiteElo"]))
    except KeyError as error:
        w_elo_list.insert(0, 0)

    try:
        b_elo_list.insert(0,int(game.headers["BlackElo"]))
    except KeyError as error:
        b_elo_list.insert(0, 0)


#Ensuring that each line has only one game, and removing the headers which provide information about the game

game_text_list_with_comments = []

headerList = ["Event","Site","Date","Round","White","Black","Result","ECO", "WhiteElo", "BlackElo","Annotator","Source","Remark"]

for line in line_list:
    line = line.replace("\n", "")
    ## this regex matches "1." but not e.g. "11." to ensure it catches the start of the game. 
    if re.match(r"^[1]\.", line) and all([False if i in line else True for i in headerList]) and line != '\n':
        game_text_list_with_comments.append(line)
    elif all([False if i in line else True for i in headerList]) and line != '\n' and line != "":
        game_text_list_with_comments[-1] = game_text_list_with_comments[-1] + " " + line
    else:
        pass

#regex to remove commentary from the games
clean_lines = []
for line in game_text_list_with_comments:
    clean_lines.append(re.sub("{\[.*?\]}"," ", line))


#Create dataframe

gamesdf = pd.DataFrame({"game": gameNum_list,
                        "year": year_list,
                        "w_elo": w_elo_list,
                        "b_elo": b_elo_list,
                        "outcome": outcome_list,
                        "moves": clean_lines
                        })
    

gamesdf["total_elo"] = gamesdf["w_elo"] + gamesdf["b_elo"]
gamesdf["inYearNumber"] = np.nan
gamesdf["topTen"] = np.nan

#Narrowing down the dataset by selecting hightest rated games

#sorted dataframe by year with best games on top for each year
gamesdf = gamesdf.sort_values(["year","total_elo"], ascending = [True, False])


allTheYears = list(np.arange(1920,2021))
yearLengths = []


#within each year, number items from 1 to however many games there were in that year.
for year in range(1920, 2021):
    number = 0
    for label, row in gamesdf.iterrows():
        if int(gamesdf.loc[label, "year"]) == year:
            gamesdf.loc[label, "inYearNumber"] = number
            number += 1
    yearLengths.append(number)

#By default the program selects the top 10% of games in each year by the total elo score of the players.
#This can be changed by changing percentageNumber below to the desired %
percentageNumber = 10

#dict of years and how many games are in the top ten percent for that year
yearTopTenNumber = {}
for key in allTheYears:
   for value in yearLengths:
      yearTopTenNumber[key] = round(value / (100/percentageNumber))


print("Step 7")
#deleting the bottom 90% of games in each year
for label, row in gamesdf[::-1].iterrows():
    #if gamesdf.loc[label, "inYearNumber"] > yearTopTenNumber[int(gamesdf.loc[label, "year"])]:
    #this line had to be changed because even 1% of games/year would have been far too many,
    # so I went with 20 games/year.
    if gamesdf.loc[label, "inYearNumber"] > 20:
        gamesdf.loc[label,"topTen"] = False
    else:
        gamesdf.loc[label, "topTen"] = True


# finalGames is a list of the top selected games from each year to iterate over
finalGames = list(gamesdf[gamesdf["topTen"]==True]["moves"])

#Analysing
print("analysing")


#defining a function to analyse the moves
# takes the arguments board and moves, where board is a 'chess.Board' type object
# and  moves is a 'chess.pgn.Game' type object
#returns a list of scores, one score per move, between -1 and 1, indicating black advantage
#and white advantage respectively.
def get_probslist(board, moves):
    probslist = []
    for move in moves:
            board.push(move)
            score = engine.analyse(board, chess.engine.Limit(depth=17))
            pscore = str(score["score"])
            centipawns = ""
            for l in pscore:
                if l == "-" or str.isdigit(l):
                    centipawns = centipawns + l
            povprob = chess.engine.Cp(int(centipawns)).wdl().expectation()
            if "Cp" in pscore:
                if "BLACK" in pscore:
                    povprob = abs(povprob -1)
                    #this line just makes it so that povprob varies between 0 and 1 where 1 is W advantage and 0 is B advantage
                    #regardless of which point of view it's from.
                absprob = (povprob*2)-1
                #this line makes absprob vary between -1 and 1 rather than between 0 and 1        
            else:
                absprob = None
            probslist.append(absprob)
    return(probslist)

# Iterating over the final selection of best games and analysing each one,
# saving the resulting list of scores, and the number of moves in the game,
# to new lists to be included in the final dataframe later.

games_analysed = 0
move_list_list = []
move_number_list = []

for gametext in finalGames:
    pgn = io.StringIO(gametext)
    game = chess.pgn.read_game(pgn)
    board = game.board()
    moves = game.mainline_moves()
    probslist = get_probslist(board, moves)
    move_list_list.append(probslist)
    move_number_list.append(len(probslist))
    games_analysed += 1
    if games_analysed % 100 == 0:
        print(str(games_analysed), " games analysed")

print("All games analysed")


#creating dataframe to save the analysis in

gamesdfFinal = gamesdf.copy()
gamesdfFinal = gamesdfFinal[gamesdfFinal.topTen == True]
gamesdfFinal["n_moves"] = move_number_list
gamesdfFinal["move_list_list"] = move_list_list

#reset indexes 
gamesdfFinal.index = [i for i in range(0,len(gamesdfFinal))]


#at this point, the move scores from the stockfish analysis are saved in a list, in a single column;
#I want the scores for each move in separate columns, which is what this chunk does:

for label, row in gamesdfFinal.iterrows():
    gamelist = move_list_list[label]
    for count, move in enumerate(gamelist):
        gamesdfFinal.loc[label, count] = move


#Save dataframe to csv

export_csv = gamesdfFinal.to_csv(r'/home/ubuntu/chessProgram/OutputFinal.csv', index = None, header=True)
print("Saved!")
