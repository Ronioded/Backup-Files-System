import server
import socket
import sys
import time
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler


# global variables.
SEPARATOR = "<SEPARATOR>"
BUFFER = 4096
ip = sys.argv[1]
port = int(sys.argv[2])
directory_path = sys.argv[3]
identification = "0000"
comp_num = "0000"


'''
the main function.
'''


def main():
    # declaring id and comp_num as globals.
    global identification, comp_num

    # open new socket and connect to the server via TCP.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))

    # if there is 4 arguments, there is no id.
    if len(sys.argv) == 4:
        # send the id and computer number to the server.
        s.send(identification.encode())
        s.send(str(comp_num).encode())

        # send all the content in the dir to the server.
        server.send_all_content(directory_path, s)
        # receiving the new id from server and updating this is the first computer.
        identification = s.recv(4).decode()
        comp_num = "0001"

    # else, there is id.
    else:
        identification = sys.argv[4]

        # send the id and computer number to the server.
        s.send(identification.encode())
        s.send(str(comp_num).encode())

        # there is id, we need to get from server all content.
        server.create_all_content(directory_path, s)

        # receive the computer number from server and send ack.
        comp_num = s.recv(4).decode()
        s.send('ack'.encode())

    # close the socket.
    s.close()
    # after all data transferring, monitor all changes in the dir.
    monitoring_changes()


'''
the function monitor all changes with watchdog.
'''


def monitoring_changes():
    # event handler- notify when something happen on the filesystem we are monitoring.
    # first argument means- we want to handle all files. Second - we do not want to ignore patterns. Third- we want
    # to handle subdirectories. Four - case sensitive.
    event_handler = PatternMatchingEventHandler(["*"], None, False, True)

    # Functions to handle changes.
    event_handler.on_created = on_created
    event_handler.on_deleted = on_deleted
    event_handler.on_moved = on_moved

    # create observer
    observer = Observer()
    observer.schedule(event_handler, directory_path, recursive=True)

    # start the observer
    observer.start()
    try:
        while True:
            # sleeping.
            time.sleep(5)
            # time passed so go to server ask for changes.
            # authenticate to server.
            s = authentication()
            # send sync request and go to update changes.
            s.send("sync".encode())
            update_changes(s)
            # close the socket.
            s.close()
    except KeyboardInterrupt:
        observer.stop()
        observer.join()


'''
the function authenticate to server and return a new socket.
'''


def authentication():
    # open a new socket and connect to server.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    # send id and computer number.
    s.send(identification.encode())
    s.send(comp_num.encode())
    # return the socket.
    return s


'''
the function is on when watchdog alarmed on create.
@event - the event happened.
'''


def on_created(event):
    # authenticate to server.
    s = authentication()
    # send create request to server.
    s.send("create".encode())
    # update changes before sending our changes to server.
    update_changes(s)
    # send the path to the server and wait for ack.
    path_to_send = event.src_path.split(directory_path)[1]
    s.send(f"{path_to_send}{SEPARATOR}{0}".encode())
    ack = s.recv(3)
    # get from server if we need to continue the operation or not.
    status = s.recv(1).decode()
    # if status equal to 1, send file or dir to server.
    if status == '1':
        server.send_file_or_dir(event.src_path, directory_path, s)
    # close socket.
    s.close()


'''
the function is on when watchdog alarmed on delete.
@event - the event happened.
'''


def on_deleted(event):
    # authenticate to server.
    s = authentication()
    # send delete request to server.
    s.send("delete".encode())
    # update changes before sending our changes to server.
    update_changes(s)
    # send server the path to delete and wait for ack.
    try:
        path_to_send = event.src_path.split(directory_path)[1]
    except (Exception,):
        path_to_send = event.src_path
    s.send(f"{path_to_send}{SEPARATOR}{0}".encode())
    ack = s.recv(3).decode()
    # receive the status, not relevant in delete.
    status = s.recv(1).decode()
    # close socket.
    s.close()


'''
the function is on when watchdog alarmed on move.
@event - the event happened.
'''


def on_moved(event):
    # authenticate to server.
    s = authentication()
    # send moved request to server.
    s.send("moved#".encode())
    # update changes before sending our changes to server.
    update_changes(s)
    # save relative paths.
    try:
        src_path = event.src_path.split(directory_path)[1]
    except (Exception,):
        src_path = event.src_path

    try:
        dst_path = event.dest_path.split(directory_path)[1]
    except (Exception,):
        dst_path = event.dest_path

    # send src_path and wait for ack.
    s.send(f"{src_path}{SEPARATOR}{0}".encode())
    ack = s.recv(3).decode()

    # get from server if continue the operation or not.
    status = s.recv(1).decode()
    # if status is 0, this is a duplicate request, so we don't continue.
    if status == '0':
        return

    # send dst_path and wait for ack.
    s.send(f"{dst_path}{SEPARATOR}{0}".encode())
    ack = s.recv(3).decode()

    # get from the server if we need to send the whole content.
    send_content_flag = s.recv(1).decode()
    # if the flag is 1, then send the content.
    if send_content_flag == '1':
        server.send_file_or_dir(event.dest_path, directory_path, s)
    # close socket.
    s.close()


'''
the function update the changes we get from server.
@s - the socket.
'''


def update_changes(s):
    # get a package from server.
    package = s.recv(6).decode()

    # while it is not donsyc, there is more changes.
    while package != "donsyc":

        # receive path and file size from server, then send ack.
        content = s.recv(BUFFER).decode()
        received_path, file_size = content.split(SEPARATOR)
        combined_path = directory_path + received_path
        s.send("ack".encode())

        # according to the package, go to the correct function.
        if package == "create":
            server.create(combined_path, file_size, s, False, '0', '0')
        elif package == "delete":
            server.delete(combined_path, False, '0', '0')
        elif package == "moved#":
            # receive the dst path from server and send ack, then go to function moved.
            content = s.recv(BUFFER).decode()
            dst_path, file_size = content.split(SEPARATOR)
            dst_combined_path = directory_path + dst_path
            ack = s.send("ack".encode())
            server.moved(combined_path, dst_combined_path, s, False, '0', '0')
        # receive the next package.
        package = s.recv(6).decode()


if __name__ == '__main__':
    main()
