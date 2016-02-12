#!/usr/bin/python

from cortex import app
import cortex.core
import cortex.views
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template

@app.workflow_handler(__name__, 'Create Sandbox VM', methods=['GET', 'POST'])
@cortex.core.login_required
def sandboxvm_create():
	# Get the list of clusters
	clusters = cortex.core.vmware_list_clusters("srv01197")

	# Get the list of environments
	environments = cortex.core.get_cmdb_environments()

	if request.method == 'GET':
		## Show form
		return render_template(__name__ + "::create.html", clusters=clusters, environments=environments, title="Create Sandbox Virtual Machine")

	elif request.method == 'POST':
		# Ensure we have all parameters that we require
		if 'sockets' not in request.form or 'cores' not in request.form or 'ram' not in request.form or 'disk' not in request.form or 'template' not in request.form or 'cluster' not in request.form or 'environment' not in request.form:
			flash('You must select options for all questions before creating', 'alert-danger')
			return redirect(url_for('sandboxvm_create'))

		# Extract all the parameters
		sockets  = request.form['sockets']
		cores    = request.form['cores']
		ram      = request.form['ram']
		disk     = request.form['disk']
		template = request.form['template']
		cluster  = request.form['cluster']
		env      = request.form['environment']
		purpose  = request.form['purpose']
		comments = request.form['comments']

		# Validate cluster against the list we've got
		if cluster not in [c['name'] for c in clusters]:
			abort(400)

		# Validate environment against the list we've got
		if env not in [e['id'] for e in environments]:
			abort(400)

		# Build options to pass to the task
		options = {}
		options['sockets'] = sockets
		options['cores'] = cores
		options['ram'] = ram
		options['disk'] = disk
		options['template'] = template
		options['cluster'] = cluster
		options['env'] = env
		options['purpose'] = purpose
		options['comments'] = comments

		# Connect to NeoCortex and start the task
		neocortex = cortex.core.neocortex_connect()
		task_id = neocortex.create_task(__name__, session['username'], options, description="Creates a virtual machine on the sandbox environment")

		# Redirect to the status page for the task
		return redirect(url_for('task_status', id=task_id))
