#!/usr/bin/python

from cortex import app
import cortex.lib.core
import cortex.lib.systems
from cortex.corpus import Corpus
from flask import Flask, request, Response, session, redirect, url_for, flash, g, abort, render_template, stream_with_context
from subprocess import Popen, PIPE, CalledProcessError
import re

#
#config
#
testcmd = "/data/cortex/cortex/bin/testssl.sh"
stdargs = ["--quiet"]
protocols = ["ftp", "smtp", "pop3", "imap", "xmpp", "telnet", "ldap"]

@app.workflow_handler(__name__, 'Test TLS/SSL', workflow_type=app.WF_SYSTEM_ACTION, workflow_desc="Tests the TLS/SSL configuration of a system")
@app.workflow_handler(__name__, 'Test TLS/SSL', workflow_desc="Tests the TLS/SSL configuration of a system")
def test(id=None):
	host=None
	if id is not None:
		system = cortex.lib.systems.get_system_by_id(id)
		if system['class'] == 'play':
			host = system['name'] + '.sandbox.soton.ac.uk'
		else:
			host = system['name'] + '.soton.ac.uk'
	return render_template(__name__ + "::test.html", host=host, title="Test SSL/TLS")

@app.workflow_route("/test", methods=['GET', 'POST'])
@cortex.lib.user.login_required
def testtls(id=None):
	host=None
	if id is not None:
		system = cortex.lib.systems.get_system_by_id(id)
		if system['class'] == 'play':
			host = system['name'] + '.sandbox.soton.ac.uk'
		else:
			host = system['name'] + '.soton.ac.uk'
	if request.method == 'GET':
		return render_template(__name__ + "::test.html", host=host, title="Test SSL/TLS")

	elif request.method == 'POST':

		#
		# validate data
		#
		valid = True


		# Host
		host = request.form['host']

		if not is_valid_host(host):
			valid = False
			flash("Invalid host")
		# Port		
		try:
			port = int(request.form['port'])
			if not 0 <= port <= 65565:
				valid = False
				flash("Invalid port")
		except:
			valid = False
			flash("Invalid port")
		
		# Starttls
		if 'starttls' in request.form and request.form['starttls'] == "yes":
			starttls = True
		else:
			starttls = False
		
		# Proto
		protocol = request.form['protocol']
		if starttls and protocol not in protocols:
			valid = False
			flash("Invalid protocol")

		# Anything failed
		if not valid:
			abort(400)

		#
		# Build command
		#

		cmd = [testcmd]
		cmd += stdargs
		if starttls:
			cmd.append("-t")
			cmd.append(protocol)
		cmd.append(host + ":" + str(port))

		#
		# GO
		#
		def scan(cmd):
			scan = Popen(cmd, stdout=PIPE, universal_newlines=True)
			for line in iter(scan.stdout.readline, ""):
				yield deansi(line)
			
			scan.stdout.close()
			return_code = scan.wait()
			if return_code != 0:
				raise CalledProcessError(return_code, cmd)
		
		return Response(stream_with_context(stream_template(__name__ + "::test.html", output=scan(cmd), styles=styleSheet(), host=host, port=port)))

###########################################################################################

def stream_template(template_name, **context):
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.enable_buffering(5)
    return rv

###########################################################################################

def is_valid_host(host):
	"""Returns true if the given host is valid"""
	hostname = re.compile("^(([a-zA-Z]|[a-zA-Z][a-zA-Z0-9-]*[a-zA-Z0-9]).)*([A-Za-z]|[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9])$", re.IGNORECASE)
	ipv4 = re.compile("^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", re.IGNORECASE)
	ipv6 = re.compile("^s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:)))(%.+)?s*", re.IGNORECASE)
	
	if hostname.match(host) or ipv4.match(host) or ipv6.match(host):
		return True
	else:
		return False





#########################################################################################

# the following was modified from 2012 David Garcia Garzon's deansi program

##########################################################################################

colorCodes = {
	0 : 'black',
	1 : 'red',
	2 : 'green',
	3 : 'yellow',
	4 : 'blue',
	5 : 'magenta',
	6 : 'cyan',
	7 :	'white',
}
attribCodes = {
	1 : 'bright',
	2 : 'faint',
	3 : 'italic',
	4 : 'underscore',
	5 : 'blink',
#	6 : 'blink_rapid',
	7 : 'reverse',
	8 : 'hide',
	9 : 'strike',
}

variations = [ # normal, pale, bright
	('black', 'black', 'gray'), 
	('red', 'darkred', 'red'), 
	('green', 'darkgreen', 'green'), 
	('yellow', 'orange', 'yellow'), 
	('blue', 'darkblue', 'blue'), 
	('magenta', 'purple', 'magenta'), 
	('cyan', 'darkcyan', 'cyan'), 
	('white', 'lightgray', 'white'), 
]

def styleSheet(brightColors=True) :
	"""\
	Returns a minimal css stylesheet so that deansi output 
	could be displayed properly in a browser.
	You can append more rules to modify this default
	stylesheet.

	brightColors: set it to False to use the same color
		when bright attribute is set and when not.
	"""

	simpleColors = [
		".ansi_%s { color: %s; }" % (normal, normal)
		for normal, pale, bright in variations]
	paleColors = [
		".ansi_%s { color: %s; }" % (normal, pale)
		for normal, pale, bright in variations]
	lightColors = [
		".ansi_bright.ansi_%s { color: %s; }" % (normal, bright)
		for normal, pale, bright in variations]
	bgcolors = [
		".ansi_bg%s { background-color: %s; }" % (normal, normal)
		for normal, pale, bright in variations]

	attributes = [
		".ansi_bright { font-weight: bold; }",
		".ansi_faint { opacity: .5; }",
		".ansi_italic { font-style: italic; }",
		".ansi_underscore { text-decoration: underline; }",
		".ansi_blink { text-decoration: blink; }",
		".ansi_reverse { border: 1pt solid; }",
		".ansi_hide { opacity: 0; }",
		".ansi_strike { text-decoration: line-through; }",
	]

	return '\n'.join(
		[ ".ansi_terminal { white-space: pre; font-family: monospace; }", ]
		+ (paleColors+lightColors if brightColors else simpleColors)
		+ bgcolors
		+ attributes
		)

def ansiAttributes(block) :
	"""Given a sequence "[XX;XX;XXmMy Text", where XX are ansi 
	attribute codes, returns a tuple with the list of extracted
	ansi codes and the remaining text 'My Text'"""

	attributeRe = re.compile( r'^[[](\d+(?:;\d+)*)?m')
	match = attributeRe.match(block)
	if not match : return [], block
	if match.group(1) is None : return [0], block[2:]
	return [int(code) for code in match.group(1).split(";")], block[match.end(1)+1:]


def ansiState(code, attribs, fg, bg) :
	"""Keeps track of the ansi attribute state given a new code"""

	if code == 0 : return set(), None, None   # reset all
	if code == 39 : return attribs, None, bg   # default fg
	if code == 49 : return attribs, fg, None   # default bg
	# foreground color
	if code in xrange(30,38) :
		return attribs, colorCodes[code-30], bg
	# background color
	if code in xrange(40,48) :
		return attribs, fg, colorCodes[code-40]
	# attribute setting
	if code in attribCodes :
		attribs.add(attribCodes[code])
	# attribute resetting
	if code in xrange(21,30) and code-20 in attribCodes :
		toRemove = attribCodes[code-20] 
		if toRemove in attribs :
			attribs.remove(toRemove)
	return attribs, fg, bg


def stateToClasses(attribs, fg, bg) :
	"""Returns css class names given a given ansi attribute state"""

	return " ".join(
		["ansi_"+attrib for attrib in sorted(attribs)]
		+ (["ansi_"+fg] if fg else [])
		+ (["ansi_bg"+bg] if bg else [])
		)

def deansi(text) :
	#text = cgi.escape(text)
	blocks = text.split("\033")
	state = set(), None, None
	ansiBlocks = blocks[:1]
	for block in blocks[1:] :
		attributeCodes, plain = ansiAttributes(block)
		for code in attributeCodes : state = ansiState(code, *state)
		classes = stateToClasses(*state)
		ansiBlocks.append(
			(("<span class='%s'>"%classes) + plain + "</span>")
			if classes else plain
			)
	text = "".join(ansiBlocks)
	return text
