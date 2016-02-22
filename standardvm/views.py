#!/usr/bin/python

from cortex import app
import cortex.lib.core
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template

@app.workflow_handler(__name__, 'Create Standard VM', 10, methods=['GET','POST'])
@cortex.lib.user.login_required
def standardvm_create():

	if request.method == 'GET':
		# Get the list of clusters
		clusters = cortex.lib.core.vmware_list_clusters("srv00080")

		# Get the list of environments
		environments = cortex.lib.core.get_cmdb_environments()

		## Show form
		return render_template(__name__ + "::create.html", clusters=clusters, environments=environments, title="Create Standard Virtual Machine")

	elif request.method == 'POST':
		# Ensure we have all parameters that we require
		if 'cpus' not in request.form or 'ram' not in request.form or 'disk' not in request.form or 'template' not in request.form or 'cluster' not in request.form or 'environment' not in request.form:
			flash('You must select options for all questions before creating', 'alert-danger')
			return redirect(url_for('standardvm_create'))

		# Extract all the parameters
		cpu      = request.form['cpus']
		ram      = request.form['ram']
		disk     = request.form['disk']
		template = request.form['template']
		cluster  = request.form['cluster']
		env      = request.form['environment']
		task     = request.form['task']
		purpose  = request.form['purpose']
		comments = request.form['comments']
		sendmail = 'send_mail' in request.form

		# Build options to pass to the task
		options = {}
		options['cpu'] = cpu
		options['ram'] = ram
		options['disk'] = disk
		options['template'] = template
		options['cluster'] = cluster
		options['env'] = env
		options['task'] = task
		options['purpose'] = purpose
		options['comments'] = comments
		options['sendmail'] = sendmail

		# Connect to NeoCortex and start the task
		neocortex = cortex.lib.core.neocortex_connect()
		task_id = neocortex.create_task(__name__, session['username'], options, description="Creates a virtual machine in the production VMware environment")

		# Redirect to the status page for the task
		return redirect(url_for('task_status', id=task_id))

