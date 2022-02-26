import socket
import sys
import random
import string
import os

# global variables.
SEPARATOR = "<SEPARATOR>"
BUFFER = 4096
id_dict = {}
no_sync_server = {}

'''
main function.
'''


def main():
    # exporting the port from arguments, create TCP socket and bind to a port.
    port = int(sys.argv[1])
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', port))
    server.listen(5)

    # id_dict is a dictionary that for each id have dictionary of computer numbers and for each computer number have
    # a dictionary that represent what operations we need to change in this computer.
    # no_sync_server is a dictionary that hold the recent changes in the clients on the server in order to avoid
    # duplicate changes.
    global id_dict, no_sync_server

    while True:
        # connect to the client.
        client_socket, client_address = server.accept()

        # get from the client the id and computer number.
        identification = client_socket.recv(4).decode()
        comp_num = client_socket.recv(4).decode()

        # if id or comp_num is 0,this is a new client or a new folder for a client.
        # else, this is a computer that connected in order to update or to export updates.
        if identification == "0000" or comp_num == "0000":
            # if identification is 0, this is a new client so receiving all files and dirs in the dir of the client.
            if identification == "0000":
                # create random id for the new client.
                identification = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
                # if this id already exists generate new id.
                while identification in id_dict:
                    identification = ''.join(random.choices(string.ascii_letters + string.digits, k=4))

                # add id to the dictionaries.
                no_sync_server[identification] = {}
                id_dict[identification] = {"0001": []}
                add_to_dict(id_dict[identification], no_sync_server[identification], "0001")

                # create new folder for this id and then getting from the client all the content inside.
                path = os.path.join('.', identification)
                os.mkdir(path)
                create_all_content(path, client_socket)

                # send the new id to the client and print it.
                client_socket.send(identification.encode())
                print(identification)

            # else, this not a new client but a new folder for a client.
            else:
                # it's an old client, so we send him all data on server.
                send_all_content(os.path.join('.', identification), client_socket)
                # send the computer number to the client- the len of the comps that already in the dictionary +1, add
                # zeros in the beginning.
                comp_num = str(len(id_dict[identification]) + 1)
                len_comp = len(comp_num)
                for i in range(len_comp, 4):
                    comp_num = "0" + comp_num
                client_socket.send(comp_num.encode())
                ack = client_socket.recv(3)

                # add the computer to the dictionary.
                add_to_dict(id_dict[identification], no_sync_server[identification], comp_num)
        else:
            # get a request from client.
            package = client_socket.recv(6).decode()
            # check for updates for this computer
            check_for_updates(id_dict[identification][comp_num], client_socket, os.path.join('.', identification))
            # monitor changes in the client.
            if package != "sync":
                monitoring(client_socket, comp_num, identification, package)
        # Client disconnected
        client_socket.close()


'''
the function add the computer to the dictionary.
@received_id_dict- the first dictionary to add to.
@no_sync_id- the second dictionary to add to. 
@comp_num- the computer number to add.
'''


def add_to_dict(received_id_dict, no_sync_id, comp_num):
    # create new dict of this computer
    received_id_dict[comp_num] = []

    # add computer to no_sync_server.
    no_sync_id[comp_num] = []


'''
function that check in the dict for the changes of this computer and notify them to client.
@changes_dict - the changes dict of a specific computer.
@client_socket - socket of the client.
@id_path - the path with the id.
'''


def check_for_updates(changes_dict, client_socket, id_path):

    # passing the keys in the changes_dict - the dict of a specific computer.
    for pair in changes_dict:
        if pair[0] == "delete":
            notify_client_delete(client_socket, pair[1], id_path)
        elif pair[0] == "create":
            notify_client_create(client_socket, pair[1], id_path)
        elif pair[0] == "moved#":
            notify_client_move(client_socket, pair[1], id_path)
    # after we make the changes, delete from the dictionary.
    changes_dict.clear()
    # send to client that we are done syncing.
    client_socket.send("donsyc".encode())


'''
the function send the client that he need to create and send the file in the path.
@client_socket - socket of the client.
@path - path to create.
@id_path - the path with the id.
'''


def notify_client_create(client_socket, path, id_path):
    # send to client he needs to create.
    client_socket.send("create".encode())
    # send file or dir.
    send_file_or_dir(path, id_path, client_socket)


'''
the function send the client that he need to delete what in the path.
@client_socket - socket of the client.
@path - path to delete.
@id_path - the path with the id.
'''


def notify_client_delete(client_socket, path, id_path):
    # send the client he needs to delete and the path to delete.
    client_socket.send("delete".encode())
    # save relative path and send it to client.
    try:
        relative_path = path.split(id_path)[1]
    except (Exception,):
        relative_path = path

    client_socket.send(f"{relative_path}{SEPARATOR}{0}".encode())
    ack = client_socket.recv(3)


'''
the function send the client that he need to move what in the path.
@client_socket - socket of the client.
@combined_path - dst and src paths.
@id_path - the path with the id.
'''


def notify_client_move(client_socket, combined_path, id_path):
    client_socket.send("moved#".encode())
    # separate the paths.
    src_path, dst_path = combined_path.split(SEPARATOR)

    # save relative paths.
    try:
        relative_src_path = src_path.split(id_path)[1]
    except (Exception,):
        relative_src_path = src_path

    try:
        relative_dst_path = dst_path.split(id_path)[1]
    except (Exception,):
        relative_dst_path = dst_path

    # send src_path, dst_path and wait for acks.
    client_socket.send(f"{relative_src_path}{SEPARATOR}{0}".encode())
    ack = client_socket.recv(3).decode()

    client_socket.send(f"{relative_dst_path}{SEPARATOR}{0}".encode())
    ack = client_socket.recv(3).decode()

    # get from the client if we need to send the whole content.
    send_content_flag = client_socket.recv(1).decode()

    # if the flag is 1, then send the content.
    if send_content_flag == '1':
        send_file_or_dir(dst_path, id_path, client_socket)


'''
the function monitor changes - change the dir in server as received.
@client_socket - socket of the client.
@comp_num - the computer number.
@received_id - the id.
@package - request from client.
'''


def monitoring(client_socket, comp_num, received_id, package):
    # flag1 represent if we need to add the change to the dictionary.
    # flag2 represent if we need to delete the src_path.
    # flag2 represent if we need to delete the dst_path.
    flag1 = True
    flag2 = False
    flag3 = False

    # receiving path from client.
    content = client_socket.recv(BUFFER).decode()
    client_socket.send("ack".encode())
    path = os.path.join('.', received_id)
    received_path, file_size = content.split(SEPARATOR)

    # combine the path with id to the relative path.
    combined_path = path + received_path

    # if the change already in the dict, delete it and ignore it because it is multiple. also send 0 to client in order
    # to announce it is multiple operation.
    if (package, combined_path) in no_sync_server[received_id][comp_num]:
        no_sync_server[received_id][comp_num].remove((package, combined_path))
        client_socket.send('0'.encode())
        return
    # send to the client it is ok to continue.
    client_socket.send('1'.encode())
    # change the file/dir in accordance to package.
    if package == "create":
        # receive the real file size.
        content = client_socket.recv(BUFFER).decode()
        client_socket.send("ack".encode())
        received_path, file_size = content.split(SEPARATOR)
        flag1, flag2 = create(combined_path, file_size, client_socket, True, received_id, comp_num)
    elif package == "delete":
        flag1, flag2 = delete(combined_path, True, received_id, comp_num)
    elif package == "moved#":
        # get a dst_path and create the file.
        content = client_socket.recv(BUFFER).decode()
        client_socket.send("ack".encode())
        relative_dst_path, file_size = content.split(SEPARATOR)
        relative_dst_path = relative_dst_path
        dst_path = path + relative_dst_path
        flag1, flag2, flag3 = moved(combined_path, dst_path, client_socket, True, received_id, comp_num)
        # change in order to add both paths to the dictionary.
        combined_path = combined_path + SEPARATOR + dst_path
    # update the dictionaries according to the flags.
    update_dictionaries_flags(flag1, flag2, flag3, comp_num, received_id, package, combined_path)


'''
the function update the dictionaries according to the flags
@flag1 - the flag represent if we did the change and need to add the dictionaries.
@flag2 - the flag represent if we need to add delete src_path to the dictionary too.
@flag3 - the flag represent if we need to add delete dst_path to the dictionary too.
@comp_num - the computer number.
@received_id - the id.
@package - request from client.
@combined_path - the path that the change happened in.
'''


def update_dictionaries_flags(flag1, flag2, flag3, comp_num, received_id, package, combined_path):
    # update the move package.
    if package == 'moved#':
        paths = combined_path.split(SEPARATOR)
        # if flag1 and flag2 is true, add the change to the dictionary.
        if flag1 and flag2:
            update_dict1(no_sync_server[received_id], id_dict[received_id], comp_num, 'delete', paths[0])
            # if flag3 is true, add delete and create on the dst_path.
            if flag3:
                update_dict1(no_sync_server[received_id], id_dict[received_id], comp_num, 'delete', paths[1])
            update_dict1(no_sync_server[received_id], id_dict[received_id], comp_num, 'create', paths[1])

    # else, if flag1 is true, add the package to the dictionary.
    elif flag1:
        update_dict1(no_sync_server[received_id], id_dict[received_id], comp_num, package, combined_path)
        # if flag2 is true, then add delete to the dictionary.
        if flag2:
            update_dict1(no_sync_server[received_id], id_dict[received_id], comp_num, 'delete', combined_path)


'''
the function add to dictionaries the change.
@no_sync_id - the dict of no_sync on this id.
@id_computers_dict - the dict of changes of computers of id.
@comp_num - the computer number.
@package - the change.
@path - the path that needed to changed.
'''


def update_dict1(no_sync_id, id_computers_dict, comp_num, package, path):
    # passing the nums in the computer numbers dictionary.
    for num in no_sync_id:
        # if this is another computer than the one that reported the change, adding this change to the dictionaries.
        if num != comp_num:
            no_sync_id[num].append((package, path))
            id_computers_dict[num].append((package, path))


'''
the function add no_sync dictionary other computers the change.
@no_sync_id - the dict of no_sync on this id.
@comp_num - the computer number.
@package - the change.
@path - the path that needed to changed.
'''


def update_dict2(no_sync_id, comp_num, package, path):
    # passing the nums in the computer numbers dictionary.
    for num in no_sync_id:
        # if this is another computer than the one that reported the change, adding this change to the dictionaries.
        if num != comp_num:
            no_sync_id[num].append((package, path))


'''
the function add all content inside the root_path and in the end the root too.
@root_path - the dir to delete.
'''


def add_all_directory(root_path, package, received_id, comp_num):
    # passing the objects in the dir.
    for ob in os.listdir(root_path):
        all_file = os.path.join(root_path, ob)
        # if it is a file, then add the file.
        if os.path.isfile(all_file):
            update_dict2(no_sync_server[received_id], comp_num, package, all_file)
        # else, add all directory.
        else:
            add_all_directory(all_file, package, received_id, comp_num)
            # add the root_path.
            update_dict2(no_sync_server[received_id], comp_num, package, all_file)


'''
the function responsible on send all bytes in a file.
@file_path - the path of the file.
@root_path - the path of the directory register to the service.
@s - the socket.
'''


def send_file(file_path, root_path, s):
    # extract the relative path and the file size.
    try:
        path_to_send = file_path.split(root_path)[1]
    except (Exception,):
        path_to_send = file_path

    file_size = os.path.getsize(file_path)
    # send the path and the file size and wait for ack.
    s.send(f"{path_to_send}{SEPARATOR}{file_size}".encode())
    ack = s.recv(3)
    # send to the other size that the package is a file.
    s.send('1'.encode())
    # open the file and reading its bytes.
    with open(file_path, "rb") as f:
        while True:
            # read the content.
            read_content = f.read(BUFFER)

            # if there is no more content, break the loop.
            if not read_content:
                ack = s.recv(3)
                break
            # send the content.
            s.send(read_content)
    # close the file.
    f.close()

'''
the function responsible on sending a directory.
@dir_path - the path of the directory to send.
@s - the socket.
'''


def send_dir(dir_path, s):
    # send to the server the dir path and wait for ack.
    s.send(f"{dir_path}{SEPARATOR}{0}".encode())
    ack = s.recv(3)

    # send 0 in order to announce this is a dir and not a file.
    s.send('0'.encode())


'''
the function responsible on sending all files and dirs in a directory
@root_path - the dir to send all files from.
@s - the socket.
'''


def send_all_content(root_path, s):
    # passing the files and dirs in root_path and send each file or dir via the socket.
    for (root, dirs, files) in os.walk(root_path, topdown=True):
        # send the files via the socket.
        for file in files:
            send_file(os.path.join(root, file), root_path, s)

        # send the dirs via the socket.
        for directory in dirs:
            send_dir(os.path.join(root, directory).split(root_path)[1], s)

    # send via the socket we are done sending the content and wait for ack.
    s.send(f"{'done'}{SEPARATOR}{0}".encode())
    ack = s.recv(3)


'''
the function receive content via the socket and creating all of it in the root_path.
@root_path - where to create the content.
@s - the socket.
'''


def create_all_content(root_path, s):
    # receive path and file size, and send ack.
    content = s.recv(BUFFER).decode()
    received_path, file_size = content.split(SEPARATOR)
    s.send("ack".encode())

    # while the path is not equal to done, receive files and dirs.
    while received_path != 'done':
        # combine the received path to the root path and create file or dir via the function responsible for it.
        combined_path = root_path + received_path
        check_create_file_dir(file_size, combined_path, s)

        # receive a new path and file size, and send ack.
        content = s.recv(BUFFER).decode()
        received_path, file_size = content.split(SEPARATOR)
        s.send("ack".encode())


'''
the function responsible of creating a file or dir.
@file_size - the file size.
@combined_path - the path to create.
@s - the socket.
'''


def check_create_file_dir(file_size, combined_path, s):
    # receive via the socket whether the package is file or directory
    is_file = s.recv(1).decode()

    # if the data is file, create new file.
    if is_file == '1':
        create_file(combined_path, file_size, s)

    # if it is a folder, create new folder.
    else:
        os.mkdir(combined_path)


'''
the function create a file with all the content received via the socket.
@combined_path - the path to create.
@file_size - the file size.
@s - the socket.
'''


def create_file(combined_path, file_size, s):
    # initializing num of bytes received.
    num_received = 0
    # create new file, and write the received content to it.
    with open(combined_path, "wb") as f:
        while True:
            # if the num_received is bigger or equal to file_size, we are done receiving the content so send ack and
            # break the loop.
            if num_received >= int(file_size):
                s.send("ack".encode())
                break

            # receive a new package, add the len of the content to num_received and write to the file.
            received_content = s.recv(BUFFER)
            num_received += len(received_content)
            f.write(received_content)
    # close the file.
    f.close()



'''
the function is fulfill a create request after monitoring changes.
@combined_path - the path to create.
@file_size - the file size.
@s - the socket.
@is_server - represent if we called the function from the server or the client.
@received_id- the id.
@comp_num - the computer number.
'''


def create(combined_path, file_size, s, is_server, received_id, comp_num):
    # flag that represent if we delete what in the path or not.
    flag = False

    # if it is existed, then delete first.
    if os.path.exists(combined_path):
        delete(combined_path, is_server, received_id, comp_num)
        flag = True
    # receive via the socket whether the package is file or directory
    is_file = s.recv(1).decode()

    # if the data is file, create new file.
    if is_file == '1':
        create_file(combined_path, file_size, s)

    # if this is a folder, create new folder, and receive all content in the folder too.
    else:
        try:
            os.mkdir(combined_path)
            create_all_content(combined_path, s)
            # if the function was called from the server, add the change int all the directory to the dictionary.
            if is_server:
                add_all_directory(combined_path, 'create', received_id, comp_num)
        except (Exception,):
            pass
    # first flag represent that we need to add the change to the dictionary. second flag represent if we deleted first.
    return True, flag


'''
the function is fulfill a delete request after monitoring changes.
@combined_path - the path to create.
@is_server - represent if we called the function from the server or the client.
@received_id- the id.
@comp_num - the computer number.
'''


def delete(combined_path, is_server, received_id, comp_num):
    # deleting only if it is existed.
    if os.path.exists(combined_path):
        # if it is a file then delete file.
        if os.path.isfile(combined_path):
            os.remove(combined_path)

        # else, remove a directory and all the content inside.
        else:
            # if the function was called from the server, add the change int all the directory to the dictionary.
            if is_server:
                add_all_directory(combined_path, 'delete', received_id, comp_num)
            delete_full_directory(combined_path)
        # first flag represent that we need to add the change to the dictionary. second flag represent that we do not
        # want to add delete to the dictionary cause this is already delete.
        return True, False
    # first flag represent that we need to add the change to the dictionary. second flag represent that we do not want
    # to add delete to the dictionary.
    return False, False


'''
the function is fulfill a moved request after monitoring changes.
@src_path - the path to delete from.
@dst_size - the path to create in.
@s - the socket.
@is_server - represent if we called the function from the server or the client.
@combined_path - the path to create.
@received_id- the id.
@comp_num - the computer number.
@return- 
first boolean return represent if we need to add the change to the dictionary.
second boolean return represent if we need to delete the src_path.
third boolean return represent if we need to delete the dst_path.
'''


def moved(src_path, dst_path, s, is_server, received_id, comp_num):
    # flag1 represent if we need to add the change to the dictionary.
    # flag2 represent if we need to delete the src_path.
    # flag3 represent if we need to delete the dst_path.
    flag1 = False
    flag2 = False
    flag3 = False

    # delete the src path, flag2 represent if we deleted the src_path.
    flag2, flag = delete(src_path, is_server, received_id, comp_num)

    if flag2:
        # send to the other side that we need to send the whole file.
        s.send('1'.encode())

        # receive the file size (and received_path too because it comes together).
        content = s.recv(BUFFER).decode()
        s.send("ack".encode())
        received_path, file_size = content.split(SEPARATOR)

        # create the file in dst_path.
        # flag1 represent if we need to add the dictionary, so if create return that we need to add, also this
        # return that. flag3 represent if we deleted the src_path, so if create return true on that, also this
        # return that.
        flag1, flag3 = create(dst_path, file_size, s, is_server, received_id, comp_num)
    # send to the other side that we do not need to send the whole file.
    s.send('0'.encode())
    # return the flags.
    return flag1, flag2, flag3


'''
the function delete all content inside the root_path and in the end the root too.
@root_path - the dir to delete.
'''


def delete_full_directory(root_path):
    # passing the objects in the dir.
    for ob in os.listdir(root_path):
        all_file = os.path.join(root_path, ob)
        # if it is a file, then delete the file.
        if os.path.isfile(all_file):
            os.remove(all_file)
        # else, delete all directory.
        else:
            delete_full_directory(all_file)

    # remove the root_path because we deleted all the content inside.
    os.rmdir(root_path)


'''
the function send file or dir.
@path - the path of the file or dir.
@root_path
@s- the socket.
'''


def send_file_or_dir(path, root_path, s):
    # if this is a file, then use send file function.
    if os.path.isfile(path):
        send_file(path, root_path, s)

    # else, use send dir function and then send all te files in the dir.
    else:
        split_path = path.split(root_path)[1]
        send_dir(split_path, s)
        send_all_content(path, s)


if __name__ == '__main__':
    main()
