import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(5)
result = s.connect_ex(('192.168.100.67', 5005))
print("Port open:" if result == 0 else "Closed")
s.close()