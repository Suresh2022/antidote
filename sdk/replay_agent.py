#!/usr/bin/env python

# This script takes a dump generated by uncommenting APDU_DUMP in
# src/communication/communication.c, and replays it against a TCP/IP manager,
# playing the Agent role.
#
# It accepts two dump formats, they can even be intermixed in the same
# file.
#
# APDU_DUMP: Each APDU begins with "send" or "recv" then one space,
# then binary data, then \n. It is semi-editable using a editor that can cope
# with binary files e.g. vi. The final \n helps humans to see APDU boundaries.
# Because this format uses APDU length to find boundaries, it does not support
# APDUs with corrupted length.
#
# Hex dump: one line per APDU. Begins with "sendh" or "recvh" followed by one
# space, then an even number of hex digits, then \n. Digits may have spaces
# between them (which are ignored). APDU length is checked but this check 
# could be disable if e.g. one wants to test with invalid-length APDUs.
#
# send/sendh mean that Manager sent that APDU. For the replay script, it
# represents the expected data from manager. The script may compare APDUs
# received from Manager with dump data, and point out the differences.
# 
# recv/recvh mean that Agent sent that APDU, so this is an APDU that the
# replay script will send to the manager.


import sys
import socket
import time

def intu16(s):
	return ord(s[0]) * 256 + ord(s[1])

def decodehex(s):
	s = s.strip().replace(" ", "")
	if (len(s) % 2):
		print "There must be an even number of hex digits"
		print s
		sys.exit(1)
	t = ""
	for i in range(0, len(s), 2):
		t = t + chr(int(s[i:i+2], 16))
	return t

def parse(s):
	tape = []
	i = 0

	while i < (len(s) - 6):
		ishex = False
		mgr_dir = s[i:i+5]
		if mgr_dir == "recv ":
			direction = "A"
		elif mgr_dir == "send ":
			direction = "M"
		elif mgr_dir == "recvh":
			direction = "A"
			ishex = True
		elif mgr_dir == "sendh":
			direction = "M"
			ishex = True
		else:
			print "Error header"
			sys.exit(1)
		i += 5

		if not ishex:
			# binary format from antidote
			choice = intu16(s[i:i+2])
			length = intu16(s[i+2:i+4])
			print direction, "0x%x" % choice, length
			if (i + length + 4) >= len(s):
				print "Underflow in apdu %d %d" % (length, i)
				sys.exit(1)

			req = 0
			invokeid = 0
			if choice == 0xe700:
				prstlen = intu16(s[i+4:i+6])
				invokeid = intu16(s[i+6:i+8])
				req = intu16(s[i+8:i+10])
				print "\t0x%x 0x%x" % (invokeid, req)

			apdu_data = s[i:i+length+4]
			i += length + 4
			i += 1 # \n
		else:
			# hex format
			j = s.find("\n", i)
			if j < 0:
				j = len(s)
			sh = s[i:j]
			ss = decodehex(sh)
			i = j + 1

			choice = intu16(ss[0:2])
			length = intu16(ss[2:4])
			print direction, "0x%x" % choice, length
			if (length + 4) > len(ss):
				print sh
				print "Underflow in hex apdu %d %d" % (length, len(ss))
				sys.exit(1)

			req = 0
			invokeid = 0
			if choice == 0xe700:
				prstlen = intu16(ss[4:6])
				invokeid = intu16(ss[6:8])
				req = intu16(ss[8:10])
				print "\t0x%x 0x%x" % (invokeid, req)

			apdu_data = ss

		apdu = {"choice": choice, "length": length, "data": apdu_data, "direction": direction,
			"invokeid": invokeid, "req": req}
		tape.append(apdu)

		if choice == 0xe300 or choice == 0xe500 or \
			(choice == 0xe700 and req >= 0x0200):
			print

	return tape

data = file(sys.argv[1]).read()
tape = parse(data)

if __name__ == "__main__":
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect(("127.0.0.1", 6024))

	print "------------------------"
	print "Playing tape..."

	for apdu in tape:
		if apdu["direction"] == "M":
			print "Expecting %04x, %d bytes" % (apdu["choice"], apdu["length"] + 4)
			recv_apdu = s.recv(65412)
			if not recv_apdu:
				print "Connection closed"
				break
			print "Received %d octets" % len(recv_apdu)
		else:
			print "Sent %04x" % apdu["choice"]
			print s.send(apdu["data"])
		time.sleep(1)

	s.close()