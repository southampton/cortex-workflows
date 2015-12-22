#!/usr/bin/python

from cortex import app
import cortex.core
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template

@app.workflow_handler(__name__, 'Standard VM', methods=['GET','POST'])
@cortex.core.login_required
def standardvm_create():

	if request.method == 'GET':
		# Get the list of clusters
		clusters = cortex.core.vmware_list_clusters("srv00080")

		# Get the list of environments
		environments = cortex.core.get_cmdb_environments()

		## Show form
		return render_template(__name__ + "::create.html", clusters=clusters, environments=environments)

	elif request.method == 'POST':
		# Ensure we have all parameters that we require
		if 'total_cpus' not in request.form or 'total_ram' not in request.form or 'total_disk' not in request.form or 'template' not in request.form or 'cluster' not in request.form or 'environment' not in request.form:
			flash('You must select options for all questions before creating', 'alert-danger')
			return redirect(url_for('standardvm_create'))

		# Extract all the parameters
		cpu      = request.form['total_cpus']
		ram      = request.form['total_ram']
		disk     = request.form['total_disk']
		template = request.form['template']
		cluster  = request.form['cluster']
		env      = request.form['environment']

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
		task_id = neocortex.create_task(__name__, session['username'], options)

		# Redirect to the status page for the task
		return redirect(url_for('task_status', id=task_id))

	
#config = app.wfsettings[__name__]
