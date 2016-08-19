#!/usr/bin/python

from cortex import app
import cortex.lib.core
import cortex.lib.systems
from cortex.corpus import Corpus
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template
from subprocess import Popen, PIPE, CalledProcessError
import re

#
#config
#
testCmd = "/data/cortex/cortex/bin/testssl.sh"
stdArgs = ["--quiet"]
checkTimeout = 90
protocols = ["ftp", "smtp", "pop3", "imap", "xmpp", "telnet", "ldap"]

@app.workflow_handler(__name__, 'testtls', workflow_type=app.WF_SYSTEM_ACTION, workflow_desc="Tests the TLS/SSL configuration of a system")
@app.workflow_handler(__name__, 'testtls', workflow_desc="Tests the TLS/SSL configuration of a system")
@cortex.lib.user.login_required
def testtls(id=None):
	if request.method == 'GET':
		return render_template(__name__ + "::menu.html", host=None, title="Test SSL/TLS")

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

		args = testsslcmd
		args += [stdargs]
		if starttls:
			args.append("-t")
			args.append(protocol)
		args.append(host + ":" + str(port))

		#
		# GO
		#
		
		try:
			test = Popen(args, stdout=PIPE, stderr=PIPE)
			out, err = check.communicate(timeout=checkTimeout)
			if test.returncode != 0:
				flash("Scan failed")
		except TimeoutExpired as e:
			flash("Scan failed")
			test.terminate()

		html = "<pre>" + str(out, 'utf-8') + "</pre>"
		
		#try:
		#	renderer = Popen([rendererCmd], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            	#	html, err = renderer.communicate(input=output, timeout=rendererTimeout)
        	#	if renderer.returncode != 0:
		#		html = "<pre>" + str(err, 'utf-8') + "</pre>"
		#		flash("HTML formatting failed with error code " + str(renderer.returncode) + " - see raw output below")
		#	except TimeoutExpired as e:
		#		flash("HTML formatting failed - see raw output below")
		#		renderer.terminate()


	return render_template(__name__ + "::results.html", output=html, title="Test TLS")

############################################################################################

def is_valid_host(host):
	"""Returns true if the given host is valid"""
	hostname = re.compile("^(([a-zA-Z]|[a-zA-Z][a-zA-Z0-9-]*[a-zA-Z0-9]).)*([A-Za-z]|[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9])$", re.IGNORECASE)
	ipv4 = re.compile("^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$", re.IGNORECASE)
	ipv6 = re.compile("^s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]d|1dd|[1-9]?d)(.(25[0-5]|2[0-4]d|1dd|[1-9]?d)){3}))|:)))(%.+)?s*", re.IGNORECASE)
	
	if hostname.match(host) or ipv4.match(host) or ipv6.match(host):
		return True
	else:
		return False
