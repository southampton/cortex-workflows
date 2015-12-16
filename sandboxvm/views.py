#!/usr/bin/python

from cortex import app
import cortex.core
import cortex.views
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template

@app.workflow_handler(__name__, 'Sandbox VM', methods=['GET', 'POST'])
@cortex.core.login_required
def sandboxvm_create():

	cpu_list = [1, 2, 4, 8]
	mem_list = [2, 4, 8, 16]
	disk_list = [0, 50, 100]

	clusters = cortex.core.vmware_list_clusters("srv01197")
	environments = cortex.core.get_cmdb_environments()

	if request.method == 'GET':
		## Show form
		return render_template(__name__ + "::create.html", cpu_list=cpu_list, mem_list=mem_list, disk_list=disk_list, clusters=clusters, environments=environments)

	elif request.method == 'POST':
		cpu      = request.form['cpu']
		ram      = request.form['ram']
		disk     = request.form['disk']
		template = request.form['template']
		cluster  = request.form['cluster']
		env      = request.form['environment']

		# Validate CPU count
		if int(cpu) not in cpu_list:
			abort(400)

		# Validate CPU count
		if int(ram) not in mem_list:
			abort(400)

		# Validate disk size
		if int(disk) not in disk_list:
			abort(400)

		# Validate cluster
		if cluster not in [c['name'] for c in clusters]:
			abort(400)

		# Validate environment
		if env not in [e['id'] for e in environments]:
			abort(400)

		# Build options
		options = {}
		options['cpu'] = cpu
		options['ram'] = ram
		options['disk'] = disk
		options['template'] = template
		options['cluster'] = cluster
		options['env'] = env

		# Connect to NeoCortex and start the task
		neocortex = cortex.core.neocortex_connect()
		task_id = neocortex.create_task(__name__, session['username'], options)

		# Redirect to the status page for the task
		return redirect(url_for('task_status', id=task_id))
