#!/usr/bin/python

from cortex import app
import cortex.lib.core
import cortex.lib.classes
import cortex.views
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template

@app.workflow_handler(__name__, 'Allocate server', 30, methods=['GET', 'POST'])
@cortex.lib.user.login_required
def allocateserver():
	# Get workflow settings
	wfconfig = app.wfsettings[__name__]

	# Get the list of enabled classes
	classes = cortex.lib.classes.list(hide_disabled=True)

	# Get the list of environments
	environments = cortex.lib.core.get_cmdb_environments()

	# Get the list of networks
	networks = wfconfig['NETWORKS']

	# Get the list of operating systems
	oses = wfconfig['OPERATING_SYSTEMS']

	if request.method == 'GET':
		## Show form
		return render_template(__name__ + "::create.html", title="Allocate new server", classes=classes, default_class="srv", environments=environments, networks=networks, oses=oses)

	elif request.method == 'POST':
		if 'purpose' not in request.form or 'comments' not in request.form or 'class' not in request.form or 'os' not in request.form or 'environment' not in request.form or 'network' not in request.form:
			flash('You must select options for all questions before allocating', 'alert-danger')
			return redirect(url_for('allocateserver'))

		# Extract all the parameters
		classname  = request.form['class']
		os         = request.form['os']
		env        = request.form['environment']
		network    = request.form['network']
		purpose    = request.form['purpose']
		comments   = request.form['comments']
		alloc_ip   = 'alloc_ip' in request.form
		is_virtual = 'is_virtual' in request.form

		# Validate class name against the list of classes
		if classname not in [c['name'] for c in classes]:
			abort(400)

		# Validate operating system
		if os not in [o['id'] for o in oses]:
			abort(400)

		# Validate environment
		if env not in [e['id'] for e in environments]:
			abort(400)

		# Validate network
		if network not in [n['id'] for n in networks]:
			abort(400)

		# Populate options
		options = {}
		options['classname'] = classname
		options['purpose'] = purpose
		options['env'] = env
		options['comments'] = comments
		options['alloc_ip'] = alloc_ip
		options['is_virtual'] = is_virtual

		# Populate network
		for net in networks:
			if net['id'] == network:
				options['network'] = net['subnet']

		# Populate OS type id
		for iter_os in oses:
			if iter_os['id'] == os:
				options['os_type'] = iter_os['type_id']

		## Connect to NeoCortex and start the task
		neocortex = cortex.lib.core.neocortex_connect()
		task_id = neocortex.create_task(__name__, session['username'], options, description="Allocate a hostname, IP address and create a CI entry")

		## Redirect to the status page for the task
		return redirect(url_for('task_status', id=task_id))
