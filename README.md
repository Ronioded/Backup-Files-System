# Backup Files System
Backup files system in Linux written in python.

Client code arguments(in order)- server IP, server port, backup directory path, (optional) ID.
When the client is running with no optional parameter, it means that the directory given by its path is a new directory to back up, so it sends all the data in the folder to the server via sockets.

When the client is running with the optional parameter, it means that the directory given by its path is not a new folder to back up, it is a folder that does not exist in the computer the code is running on, but the client (that his ID was entered) already have a directory in the server so we need to synchronize the directory from the server to the directory that given by its path.

After the data transferring in each option, the client code is monitoring changes in the directory registered to the service. Every creation, delete, movement of a file or directory in the registered directory or sub-directories are being saved at the server and synchronized in all other computers of the client registered to the service.

A computer is updating changes from the server in 2 options: 
1. something changed in a computer's directory so the program updates the server about the changes to back them up. Before that, the server updates changes from other computers to that computer.
2. every 5 seconds the program approaches the server to update the changes from other computers.

Server code arguments- port number. The server is accepting clients one after another (not in parallel). Each client has an ID which is a coding combined from 4 numbers or letters. The server assigns an ID in the connection of the first computer. From now on, for each connection from a new computer to a directory, we need to put as a parameter the ID received while connecting from the first computer - the ID is being printed after assignment.
Every change in every computer of the client is being notified to the server that updates it in a directory where the server code appears.

Not have support in conflicting changes. For example, 2 computers did a change in the same file/directory at the same time. 
Do have support when one computer did a change, the other computer updates the changes from the server, and then does a change and updates the server.
