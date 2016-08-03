#!/usr/bin/python

from cortex import app
import cortex.lib.core
import cortex.views
import datetime
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template

################################################################################
## Sandbox VM Workflow view handler

@app.workflow_handler(__name__, 'Create Sandbox VM', 20, methods=['GET', 'POST'])
@cortex.lib.user.login_required
def sandbox():
	# Get the list of clusters
	clusters = cortex.lib.core.vmware_list_clusters("srv01197")

	# Get the list of environments
	environments = cortex.lib.core.get_cmdb_environments()

	# Get the workflow settings
	wfconfig = app.wfsettings[__name__]

	if request.method == 'GET':
		## Show form
		return render_template(__name__ + "::sandbox.html", clusters=clusters, environments=environments, title="Create Sandbox Virtual Machine", default_env='dev', default_cluster='CHARTREUSE', os_names=wfconfig['SB_OS_DISP_NAMES'], os_order=wfconfig['SB_OS_ORDER'])

	elif request.method == 'POST':
		# Ensure we have all parameters that we require
		if 'sockets' not in request.form or 'cores' not in request.form or 'ram' not in request.form or 'disk' not in request.form or 'template' not in request.form or 'environment' not in request.form:
			flash('You must select options for all questions before creating', 'alert-danger')
			return redirect(url_for('sandbox'))
		
		# Form validation
		try:
			# Extract all the parameters
			purpose  = request.form['purpose']
			comments = request.form['comments']
			sendmail = 'send_mail' in request.form

			# Validate the data (common between standard / sandbox)
			(sockets, cores, ram, disk, template, env, expiry) = validate_data(request, wfconfig['OS_ORDER'], [e['id'] for e in environments])

			return redirect(url_for('sandbox'))
		except ValueError as e:
			flash(str(e), 'alert-danger')
			return redirect(url_for('sandbox'))

		except Exception as e:
			flash('Submitted data invalid ' + str(e), 'alert-danger')
			return redirect(url_for('sandbox'))
				
		# Build options to pass to the task
		options = {}
		options['workflow'] = 'sandbox'
		options['sockets'] = sockets
		options['cores'] = cores
		options['ram'] = ram
		options['disk'] = disk
		options['template'] = template
		#options['cluster'] = cluster	## Commenting out whilst we only have one cluster
		options['cluster'] = 'CHARTREUSE'
		options['env'] = env
		options['purpose'] = purpose
		options['comments'] = comments
		options['expiry'] = expiry
		options['sendmail'] = sendmail
		options['wfconfig'] = wfconfig

		# Connect to NeoCortex and start the task
		neocortex = cortex.lib.core.neocortex_connect()
		task_id = neocortex.create_task(__name__, session['username'], options, description="Creates and sets up a virtual machine (sandbox VMware environment)")

		# Redirect to the status page for the task
		return redirect(url_for('task_status', id=task_id))

################################################################################
## Standard VM Workflow view handler

@app.workflow_handler(__name__, 'Create Standard VM', 10, methods=['GET','POST'])
@cortex.lib.user.login_required
def standard():
	# Get the workflow settings
	wfconfig = app.wfsettings[__name__]

	# Get the list of clusters
	all_clusters = cortex.lib.core.vmware_list_clusters("srv00080")

	# Exclude any clusters that the config asks to:
	clusters = []
	for cluster in all_clusters:
		if cluster['name'] not in wfconfig['HIDE_CLUSTERS']:
			clusters.append(cluster)

	# Get the list of environments
	environments = cortex.lib.core.get_cmdb_environments()

	if request.method == 'GET':
		## Show form
		return render_template(__name__ + "::standard.html", clusters=clusters, environments=environments, os_names=wfconfig['OS_DISP_NAMES'], os_order=wfconfig['OS_ORDER'], title="Create Standard Virtual Machine")

	elif request.method == 'POST':
		# Ensure we have all parameters that we require
		if 'sockets' not in request.form or 'cores' not in request.form or 'ram' not in request.form or 'disk' not in request.form or 'template' not in request.form or 'cluster' not in request.form or 'environment' not in request.form:
			flash('You must select options for all questions before creating', 'alert-danger')
			return redirect(url_for('standard'))

		# Form validation
		try:
			# Extract the parameters (some are extracted by validate_data)
			cluster  = request.form['cluster']
			task     = request.form['task']
			purpose  = request.form['purpose']
			comments = request.form['comments']
			sendmail = 'send_mail' in request.form

			# Validate the data (common between standard / sandbox)
			(sockets, cores, ram, disk, template, env, expiry) = validate_data(request, wfconfig['OS_ORDER'], [e['id'] for e in environments])

			# Validate cluster against the list we've got
			if cluster not in [c['name'] for c in clusters]:
				raise ValueError('Invalid cluster selected')

		except ValueError as e:
			flash(str(e), 'alert-danger')
			return redirect(url_for('standard'))

		except Exception as e:
			flash('Submitted data invalid', 'alert-danger')
			return redirect(url_for('standard'))
	
		# Build options to pass to the task
		options = {}
		options['workflow'] = 'standard'
		options['sockets'] = sockets
		options['cores'] = cores
		options['ram'] = ram
		options['disk'] = disk
		options['template'] = template
		options['cluster'] = cluster
		options['env'] = env
		options['task'] = task
		options['purpose'] = purpose
		options['comments'] = comments
		options['sendmail'] = sendmail
		options['wfconfig'] = wfconfig
		options['expiry'] = expiry
		if 'NOTIFY_EMAILS' in app.config:
			options['notify_emails'] = app.config['NOTIFY_EMAILS']
		else:
			options['notify_emails'] = []

		# Connect to NeoCortex and start the task
		neocortex = cortex.lib.core.neocortex_connect()
		task_id = neocortex.create_task(__name__, session['username'], options, description="Creates and sets up a virtual machine (standard VMware environment)")

		# Redirect to the status page for the task
		return redirect(url_for('task_status', id=task_id))

################################################################################
## Common data validation / form extraction

def validate_data(r, templates, envs):
	# Pull data out of request
	sockets  = r.form['sockets']
	cores	 = r.form['cores']
	ram	 = r.form['ram']
	disk	 = r.form['disk']
	template = r.form['template']
	env	 = r.form['environment']

	sockets = int(sockets)
	if not 1 <= sockets <= 16:
		raise ValueError('Invalid number of sockets selected')

	cores = int(cores)
	if not 1 <= cores <= 16:
		raise ValueError('Invalid number of cores per socket selected')

	ram = int(ram)
	if not 2 <= ram <= 32:
		raise ValueError('Invalid amount of RAM selected')
	
	disk = int(disk)
	if not 100 <= disk <= 2000:
		raise ValueError('Invalid disk capacity selected')
	
	if template not in templates:
		raise ValueError('Invalid template selected')
	
	if env not in envs:
		raise ValueError('Invalid environment selected')

	if 'expiry' in r.form and r.form['expiry'] is not None and len(r.form['expiry'].strip()) > 0:
		expiry = r.form['expiry']
		try:
			expiry = datetime.datetime.strptime(expiry, '%Y-%m-%d')
		except Exception, e:
			raise ValueError('Expiry date must be specified in YYYY-MM-DD format')
	else:
		expiry = None

	return (sockets, cores, ram, disk, template, env, expiry)
