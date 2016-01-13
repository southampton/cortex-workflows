#!/usr/bin/python

from cortex import app
import cortex.core
import cortex.views
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template

@app.workflow_handler(__name__, 'Sandbox VM', methods=['GET', 'POST'])
@cortex.core.login_required
def sandboxvm_create():
	# Define what CPU, RAM and Disk specs we can have
	cpu_list = [1, 2, 4, 8]
	mem_list = [2, 4, 8, 16]
	disk_list = [0, 50, 100]

	# Get the list of clusters
	clusters = cortex.core.vmware_list_clusters("srv01197")

	# Get the list of environments
	environments = cortex.core.get_cmdb_environments()

	if request.method == 'GET':
		## Show form
		return render_template(__name__ + "::create.html", cpu_list=cpu_list, mem_list=mem_list, disk_list=disk_list, clusters=clusters, environments=environments)

	elif request.method == 'POST':
		# Ensure we have all parameters that we require
		if 'cpu' not in request.form or 'ram' not in request.form or 'disk' not in request.form or 'template' not in request.form or 'cluster' not in request.form or 'environment' not in request.form:
			flash('You must select options for all questions before creating', 'alert-danger')
			return redirect(url_for('sandboxvm_create'))

		# Extract all the parameters
		cpu      = request.form['cpu']
		ram      = request.form['ram']
		disk     = request.form['disk']
		template = request.form['template']
		cluster  = request.form['cluster']
		env      = request.form['environment']

		# Validate CPU count against our defined list
		if int(cpu) not in cpu_list:
			abort(400)

		# Validate CPU count against our defined list
		if int(ram) not in mem_list:
			abort(400)

		# Validate disk size against our defined list
		if int(disk) not in disk_list:
			abort(400)

		# Validate cluster against the list we've got
		if cluster not in [c['name'] for c in clusters]:
			abort(400)

		# Validate environment against the list we've got
		if env not in [e['id'] for e in environments]:
			abort(400)

		# Build options to pass to the task
		options = {}
		options['cpu'] = cpu
		options['ram'] = ram
		options['disk'] = disk
		options['template'] = template
		options['cluster'] = cluster
		options['env'] = env

		# Connect to NeoCortex and start the task
		neocortex = cortex.core.neocortex_connect()
		task_id = neocortex.create_task(__name__, session['username'], options, description="Creates a virtual machine on the sandbox environment")

		# Redirect to the status page for the task
		return redirect(url_for('task_status', id=task_id))
