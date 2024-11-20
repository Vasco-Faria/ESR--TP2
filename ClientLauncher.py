import sys
from tkinter import Tk
from Client import Client

if __name__ == "__main__":
		
	root = Tk()
	
	# Create the  client
	app = Client(root)
	app.master.title("RTPClient")	
	root.mainloop()
	