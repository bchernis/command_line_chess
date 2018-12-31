#! /usr/bin/python

import getpass
import socket
import sys
import getpass
import json
import time
from thread import *
import pickle


size = 1024
outbox = [] #This will act as a FIFO queue

def toJSON(input, username, password):
	#Need pickle, because json output is in dictionary format
	return pickle.dumps(json.loads(json.dumps({'username':username, 'password':password, 'request':input})))
	
def receiveThread(s, username, password):
	while 1:
		buffer = s.recv(size)
		if buffer:
			print (buffer)

def sendThread(s, username, password): #Server will never send message until client sends message
	while 1:
		try:
			time.sleep(.5) #To avoid hogging the CPU
			if outbox:
				s.send(toJSON(outbox[0], username, password))
				del outbox[0]
			else:
				s.send(toJSON("UPDATE", username, password)) #Check if server has any messages for this client
		except:
			print ("Exception encountered")

def commandThread(s):
	while 1:	
		outbox.append(raw_input())

host = sys.argv[1]
port = int(sys.argv[2])

while 1:
	while 1:
		option = int(raw_input("Enter 1 to login or 2 to create a new account: "))
		username = raw_input("Username: ")
		password = getpass.getpass("Password: ") #Hides text that is being typed
		if (option != 1 and option != 2) or len(username.split()) != 1 or \
		len(password.split()) != 1 or len(username.split()[0]) != len(username) or \
		len(password.split()[0]) != len(password):
			print ("Choose a valid option, and enter a 1-word username and password (with no spaces).")
			continue
		break
	
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect((host, port))

	if option == 2:
		s.send("CREATE_ACCOUNT " + username + " " + password)
		buffer = s.recv(size)
		if (buffer == "USERNAME_EXISTS"):
			s.send("LOGOUT")
			s.close()
			print ("That username already exists.")
		else:
			print (buffer)
			break
	else:
		s.send("LOGIN " + username + " " + password)
		buffer = s.recv(size)
		if buffer =="WRONG_LOGIN":
			print ("Wrong username and/or password.")
		if buffer =="DUPLICATE_LOGIN":
			print ("You are already logged in.")
		else:
			print (buffer)
			break
try:
	start_new_thread(sendThread,(s, username, password))
	start_new_thread(receiveThread,(s, username, password))
	start_new_thread(commandThread,(s,))
	time.sleep(1000000000) #Threads can run for up to a billion seconds
except:
	s.send("LOGOUT")
	s.close()
	exit()