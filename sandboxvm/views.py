#!/usr/bin/python

from cortex import app, NotFoundError, DisabledError
import cortex.core
import cortex.views
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template

@app.workflow_handler(__name__, 'Sandbox VM', methods=['GET','POST'])
@cortex.core.login_required
def sandboxvm_create():

	if request.method == 'GET':
		## Show form
		return render_template(__name__ + "::create.html")

	elif request.method == 'POST':
		cpu = request.form['cpu']
		ram = request.form['ram']
		disk = request.form['disk']
		template = request.form['template']

		## TODO validate form
		## work out what to do

		options = {}
		options['cpu'] = cpu
		options['ram'] = ram
		options['disk'] = disk
		options['template'] = template

		neocortex = cortex.core.neocortex_connect()
		task_id = neocortex.create_task(__name__,session['username'],options)
		return redirect(url_for('task_status',id=task_id))
