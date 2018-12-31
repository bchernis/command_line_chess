#! /usr/bin/python 

import select 
import socket 
import sys 
import chess
import hashlib
import pickle
import json
import random
import os

host = sys.argv[1]
port = int(sys.argv[2])
backlog = 5 
size = 1024 
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
server.bind((host,port)) 
server.listen(backlog) 
input = [server,sys.stdin] 
running = 1 

allSockets = {}
allGames = []

WHITE = "white"
BLACK = "black"
USERNAME = "username"
RATING = "rating"
OUTBOX = "outbox"
POSITION = "position"
DRAW_OFFERED = "drawOffered"
RESULT = "result"
PASSWORD = "password"
GAME_INDEX = "gameIndex"
KIBITZERS = "kibitzers"
STATUS = "status"

def updateRatings (whiteSocket, blackSocket, result):
	#Assign the users new ratings, based on the result of their game (both in the socket dictionary and in usernames.txt)
	K = 50.0
	whiteUsername = allSockets[whiteSocket][USERNAME]
	blackUsername = allSockets[blackSocket][USERNAME]
	whiteRating = int(allSockets[whiteSocket][RATING])
	blackRating = int(allSockets[blackSocket][RATING])
	r1 = float(whiteRating)
	r2 = float(blackRating)
	R1 = pow(10, r1 / 400)
	R2 = pow(10, r2 / 400)
	E1 = R1 / (R1 + R2)
	E2 = 1 - E1
	if result == WHITE:
		S1 = 1
	elif result == BLACK:
		S1 = 0
	else:
		S1 = .5
	S2 = 1 - S1
	rPrime1 = r1 + K * (S1 - E1)
	rPrime2 = r2 + K * (S2 - E2)
	allSockets[whiteSocket][RATING] = str(int(round(rPrime1)))
	allSockets[blackSocket][RATING] = str(int(round(rPrime2)))
	text1 = whiteUsername + " " + str(whiteRating)
	text2 = whiteUsername + " " + str(allSockets[whiteSocket][RATING])
	os.system("sed -ie 's/" + text1 + "/" + text2 + "/g' usernames.txt") #Replace old rating with new rating in text file
	text1 = blackUsername + " " + str(blackRating)
	text2 = blackUsername + " " + str(allSockets[blackSocket][RATING])
	os.system("sed -ie 's/" + text1 + "/" + text2 + "/g' usernames.txt")

def userExists (username):
	os.system("touch usernames.txt") #Make sure this file exists
	with open("usernames.txt", "r") as fin:
		userTable = fin.readlines()
	for userRow in userTable:
		if username == userRow.split()[0]:
			return True
	return False

def checkUserInfo (username):
	with open("usernames.txt", "r") as fin: #Read username/hash file into a list
		userTable = fin.readlines()
	for userRow in userTable: #Perform linear search for username
		if username == userRow.split()[0]: #Extract first word from each line
			return int(userRow.split()[1]), userRow.split()[2] #Return second word (rating) and third word (hashed password) from each line 
	return "" #If username does not exist

def checkDuplicateLogin (username):
	for i in allSockets:
		if allSockets[i][USERNAME] == username:
			return True
	return False
						
#There are several different functions to send someone a message
def send2currentSocket(message): #Send to outbox of current socket
	allSockets[s][OUTBOX].append(message)

def send2user(targetUser, message): #Send to outbox of arbitrary socket, based on username
	allSockets[findSocket(targetUser)][OUTBOX].append(message)

def send2socket(targetUserSocket, message): #Here, the socket is provided as an argument. 
	allSockets[targetUserSocket][OUTBOX].append(message)

def findSocket (username):
	for target in allSockets:
		if allSockets[target][USERNAME] == username:
			return target
	return 0

#Remove first few words from a string
def removeWords(inString, numwords):
	counter = 0
	outString = ""
	for i in range(numwords,len(inString.split())):
		outString += inString.split()[i] + " "
	return outString[0:len(outString)-1] #Remove last space

#When a chess move occurs
def chessMove(moveEntry):
	gameIndex = allSockets[s][GAME_INDEX]
	thisGame = allGames[gameIndex]
	if s == thisGame[WHITE]:
		myColor = WHITE
	if s == thisGame[BLACK]:
		myColor = BLACK
	if thisGame[POSITION].turn:
		activePlayerSocket = thisGame[WHITE]
		waitingPlayerSocket = thisGame[BLACK]
	else:
		activePlayerSocket = thisGame[BLACK]
		waitingPlayerSocket = thisGame[WHITE]
	
	if moveEntry == "RESIGN": #Resigning does not change the board position
		if s is not activePlayerSocket:
			thisGame[POSITION].turn = not thisGame[POSITION].turn #So that you can't "resign" your opponent if it is not your turn	
	elif moveEntry == "DRAW":
		if allGames[gameIndex][DRAW_OFFERED] == "none" and myColor == WHITE:
			allGames[gameIndex][DRAW_OFFERED] = WHITE
			allSockets[thisGame[BLACK]][OUTBOX].append("A draw has been offered.")
		if allGames[gameIndex][DRAW_OFFERED] == "none" and myColor == BLACK:
			allGames[gameIndex][DRAW_OFFERED] = BLACK
			allSockets[thisGame[WHITE]][OUTBOX].append("A draw has been offered.")
		elif allGames[gameIndex][DRAW_OFFERED] == WHITE and myColor == BLACK or allGames[gameIndex][DRAW_OFFERED] == BLACK and myColor == WHITE:
			allGames[gameIndex][RESULT] = "draw"
					
	else:
		allGames[gameIndex][DRAW_OFFERED] = "none"
		if s is not activePlayerSocket:
			send2currentSocket("Wait for your turn!!")
			return
	
		letter1 = moveEntry[0:1]
		letter2 = moveEntry[1:2]
		letter3 = moveEntry[2:3]
		letter4 = moveEntry[3:4]
		
		#Make sure coordinates are not out-of-bounds (chess library does not check this automatically)
		if len(moveEntry) != 4 or letter1 < "a" or letter1 > "h" or letter3 < "a" or letter3 > "h" or letter2 < "1" or letter2 > "8" or letter4 < "1" or letter4 > "8":
			send2currentSocket("Please make a legal move!!!") 
			return
		
		move = chess.Move.from_uci(moveEntry)
		
		#Note: thisGame is a copy, NOT a pointer, so we do NOT modify it
		if move in thisGame[POSITION].legal_moves: #If the move is legal
			allGames[gameIndex][POSITION].push(move) #Make the move
			thisGame = allGames[gameIndex] #Update thisGame, since thisGame is a clone, and the position has changed
			send2user(allSockets[activePlayerSocket][USERNAME], str(thisGame[POSITION])+"\n")
			send2user(allSockets[waitingPlayerSocket][USERNAME], str(thisGame[POSITION])+"\n")
			for k in allGames[gameIndex][KIBITZERS]:
				send2user(allSockets[k][USERNAME], str(thisGame[POSITION])+"\n")
		else:
			send2currentSocket("Please make a legal move!!!")
			return
			
	if thisGame[POSITION].is_checkmate() or moveEntry is "RESIGN":
		if thisGame[POSITION].turn:
			message = "Black won."
			allGames[gameIndex][RESULT] = BLACK
		else:
			message = "White won."
			allGames[gameIndex][RESULT] = WHITE
		allGames[gameIndex][STATUS] = "ended"
	elif allGames[gameIndex][RESULT] == "draw" or thisGame[POSITION].is_stalemate() or allGames[0][POSITION].is_insufficient_material() or allGames[0][POSITION].can_claim_threefold_repetition() or allGames[0][POSITION].can_claim_fifty_moves():
		message = "It's a draw!!"
		allGames[gameIndex][RESULT] = "draw"
		allGames[gameIndex][STATUS] = "ended"
	else:
		if (thisGame[POSITION].turn):
			message = "White to move."
		else:
			message = "Black to move."
			
	if message: #If there is a message about the game result, send message, and change gameIndex of all players to -1
		send2user(allSockets[activePlayerSocket][USERNAME], message)
		send2user(allSockets[waitingPlayerSocket][USERNAME], message)
		allSockets[activePlayerSocket][GAME_INDEX] = -1
		allSockets[waitingPlayerSocket][GAME_INDEX] = -1
		for k in allGames[gameIndex][KIBITZERS]:
			allSockets[k][GAME_INDEX] = -1 #Send kibitzers back to lobby
			send2user(allSockets[k][USERNAME], message)
	
	if allGames[gameIndex][RESULT]:
		updateRatings(allGames[gameIndex][WHITE], allGames[gameIndex][BLACK], allGames[gameIndex][RESULT])

while running:
	inputready,outputready,exceptready = select.select(input,[],[])
	for s in inputready:
		if s == server:
			# handle the server socket
			client, address = server.accept()
			input.append(client)

		elif s == sys.stdin:
			# handle standard input
			junk = sys.stdin.readline()
			try:
				exec(junk) #Excellent for debugging
			except:
				print ("Error.")
		else:
			request_raw = s.recv(size)
			if request_raw:
				verified = 0
				username_verify = password_verify = ""
				if request_raw[0:1] == "(":
					request = json.dumps(pickle.loads(request_raw)['request']).replace("\"","")
					username_verify = json.dumps(pickle.loads(request_raw)[USERNAME]).replace("\"","")
					password_verify = json.dumps(pickle.loads(request_raw)[PASSWORD]).replace("\"","")
				else:
					request = request_raw
				command = request.split()[0] #First word of request is the command
				
				if s not in allSockets:
					allSockets[s] = {OUTBOX:[], GAME_INDEX:-1, USERNAME:'', PASSWORD:''}
				else:
					if username_verify == allSockets[s][USERNAME] and password_verify == allSockets[s][PASSWORD]:
						verified = 1 #Identity confirmed
						
				if command == "UPDATE" and verified:
					if any(allSockets[s][OUTBOX]):
						s.send(allSockets[s][OUTBOX][0])
						del allSockets[s][OUTBOX][0]
				elif command == "CREATE_ACCOUNT" and len(request.split()) > 2:
					username = request.split()[1]
					password = request.split()[2]
					if userExists(username):
						s.send("USERNAME_EXISTS")
					else:
						passwordHash = hashlib.md5()
						passwordHash.update(password)
						with open("usernames.txt", "a") as fout: #Append username/password hash to usernames.txt
							fout.write(username + " 1200 " + passwordHash.hexdigest() + "\n")
						allSockets[s][USERNAME] = username
						allSockets[s][PASSWORD] = password
						allSockets[s][RATING] = "1200"
						s.send("Account created. You logged in as " + username + ".")
				elif command == "LOGIN" and len(request.split()) > 2:
					username = request.split()[1]
					password = request.split()[2]
					passwordHash = hashlib.md5()
					passwordHash.update(password)
					if not userExists(username) or passwordHash.hexdigest() != checkUserInfo(username)[1]:
						s.send("WRONG_LOGIN")
					elif checkDuplicateLogin(username):
						s.send("DUPLICATE_LOGIN")
					else:
						allSockets[s][USERNAME] = username
						allSockets[s][PASSWORD] = password
						allSockets[s][RATING] = str(checkUserInfo(username)[0])
						s.send("You logged in as " + username + ".")
				elif command == "LOGOUT" and verified:
					gameIndex = allSockets[s][GAME_INDEX]
					if gameIndex >= 0:
						if s is allGames[gameIndex][WHITE] or s is allGames[gameIndex][BLACK]:
							chessMove("RESIGN")
					del allSockets[s]
					s.close()
					input.remove(s)
				elif command == "LIST_USERS" and verified:
					allUsers = "The following users are logged in:\n"
					for i in allSockets:
						allUsers += allSockets[i][USERNAME] + " " + allSockets[i][RATING] + "\n"
					send2currentSocket(allUsers)
				elif command == "TEXT" and len(request.split()) > 2 and verified:
					targetUser = request.split()[1]
					message = allSockets[s][USERNAME] + " says: " + removeWords(request, 2) #Remove first 2 words
					if findSocket(targetUser):
						send2user(targetUser, message)
					else:
						send2currentSocket("That user is not logged in.")
				elif command == "INVITE" and len(request.split()) > 1 and verified:
					targetUser = request.split()[1]
					if findSocket(targetUser) and findSocket(targetUser) is not s:
						gameIndex = len(allGames)
						allGames.append({POSITION:chess.Board(), WHITE:s, BLACK:findSocket(targetUser),\
						STATUS:'waiting', DRAW_OFFERED:'none', KIBITZERS:[], RESULT:''})
						allSockets[s][GAME_INDEX] = allSockets[findSocket(targetUser)][GAME_INDEX] = gameIndex #Assign both users to the game
						message = allSockets[s][USERNAME] + " has invited you to a game. Please enter \"ACCEPT\" if you want to play."
						send2user(targetUser, message)
					else:
						send2currentSocket("You may not invite yourself or users who are not logged in.")
				elif command == "UNINVITE" and verified:
					gameIndex = allSockets[s][GAME_INDEX]
					if allSockets[s][GAME_INDEX] != -1 and allGames[gameIndex][STATUS] == "waiting":
						targetUserSocket = allGames[gameIndex][BLACK]
						allSockets[s][GAME_INDEX] = allSockets[targetUserSocket][GAME_INDEX] = -1 #Take both users back to the lobby
						message = "You have been uninvited."
						send2socket(targetUserSocket, message)
						allGames[gameIndex][STATUS] = "ended"
					else:
						send2currentSocket("You cannot uninvite.")
				elif command == "ACCEPT" and verified:
					message = allSockets[s][USERNAME] + " has accepted your challenge."
					targetUser = allSockets[allGames[allSockets[s][GAME_INDEX]][WHITE]][USERNAME]
					allGames[allSockets[s][GAME_INDEX]][STATUS] = "active"
					send2user(targetUser, message)
					#Send position to players
					send2currentSocket(str(allGames[allSockets[s][GAME_INDEX]][POSITION]))
					send2user(targetUser, str(allGames[allSockets[s][GAME_INDEX]][POSITION]))
					if random.randint(0,1): #Switch white and black with 50% probability so that inviter is not white 100% of the time
						allGames[allSockets[s][GAME_INDEX]][WHITE], allGames[allSockets[s][GAME_INDEX]][BLACK] = \
						allGames[allSockets[s][GAME_INDEX]][BLACK], allGames[allSockets[s][GAME_INDEX]][WHITE]
					#Tell white to move
					white = allSockets[allGames[allSockets[s][GAME_INDEX]][WHITE]][USERNAME]
					black = allSockets[allGames[allSockets[s][GAME_INDEX]][BLACK]][USERNAME]
					send2user(white, "You are white. Your move.")
					send2user(black, "You are black. It is white's move.")
				elif command == "DECLINE" and verified:
					message = allSockets[s][USERNAME] + " has declined your challenge."
					targetUser = allSockets[allGames[allSockets[s][GAME_INDEX]][WHITE]][USERNAME]
					allGames[allSockets[s][GAME_INDEX]][STATUS] = "ended"
					allSockets[s][GAME_INDEX] = allSockets[findSocket(targetUser)][GAME_INDEX] = -1 #Take players back to "lobby"
					send2user(targetUser, message)
				elif command == "MOVE" and len(request.split()) > 1 and verified:
					moveEntry = request.split()[1]
					chessMove(moveEntry)
				elif command == "LIST_GAMES" and verified:
					if len(allGames) == 0:
						send2currentSocket("There are no active games right now.")
					else:
						for i in range(0,len(allGames)):
							if allGames[i][STATUS] == "active":
								send2currentSocket("Game " + str(i) + ": " + allSockets[allGames[i][WHITE]][USERNAME] + " vs " + allSockets[allGames[i][BLACK]][USERNAME])
				elif command == "KIBITZ_START" and len(request.split()) > 1 and verified:
					gameIndex = int(request.split()[1])
					if gameIndex < len(allGames) and allGames[gameIndex][STATUS] == "active":
						allSockets[s][GAME_INDEX] = allSockets[findSocket(targetUser)][GAME_INDEX] = gameIndex
						send2currentSocket(str(allGames[allSockets[s][GAME_INDEX]][POSITION]))
						if allGames[allSockets[s][GAME_INDEX]][POSITION].turn:
							send2currentSocket("White to move.")
						else:
							send2currentSocket("Black to move.")
						#allGames[gameIndex][KIBITZERS].append(allSockets[s]) #Add to kibitzer sockets for that game
						allGames[gameIndex][KIBITZERS].append(s) #Add to kibitzer sockets for that game
					else:
						send2currentSocket("This is not an active game.")
				elif command == "KIBITZ_STOP":
					allSockets[s][GAME_INDEX] = allSockets[findSocket(targetUser)][GAME_INDEX] = -1 #Take kibitzer back to lobby
					allGames[gameIndex][KIBITZERS].remove(s) #Remove kibitzer's socket from the game
				elif command == "RESIGN":
					chessMove("RESIGN")
				elif command == "DRAW":
					chessMove("DRAW")
				else:
					send2currentSocket("Invalid command!!")

server.close()