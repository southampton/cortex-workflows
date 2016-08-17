#!/usr/bin/python

from cortex import app
import cortex.lib.core
import cortex.lib.systems
from cortex.corpus import Corpus
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template
from pyVmomi import vim
from itsdangerous import JSONWebSignatureSerializer

# Check if an AD object exists
## Delete it

@app.workflow_handler(__name__, 'Decommission', workflow_type=app.WF_SYSTEM_ACTION, workflow_desc="Begins the process of decommissioning this system.")
@cortex.lib.user.login_required
def decom_step1(id):
	system = cortex.lib.systems.get_system_by_id(id)
	if system is None:
		abort(404)
	
	return render_template(__name__ + "::step1.html", system=system, title="Decommission Node")

@app.workflow_route("/<int:id>")
@cortex.lib.user.login_required
def decom_step2(id):
	# in this step we work out what steps to perform
	# then we load this into a list of steps, each step being a dictionary
	# this is used on the page to list the steps to the user
	# the list is also used to generate a JSON document which we sign using
	# app.config['SECRET_KEY'] and then send that onto the page as well.

	# load the corpus library
	corpus = Corpus(g.db,app.config)

	system = cortex.lib.systems.get_system_by_id(id)
	if system is None:
		abort(404)

	actions = []

	systemenv = None
	## Find the environment that this VM is in based off of the CMDB env
	if 'cmdb_environment' in system:
		if system['cmdb_environment'] is not None:
			for env in app.config['ENVIRONMENTS']:
				if env['name'] == system['cmdb_environment']:
					# We found the environment matching the system
					systemenv = env
					break
					

	## Is the system linked to vmware?
	if 'vmware_uuid' in system:
		if system['vmware_uuid'] is not None:
			if len(system['vmware_uuid']) > 0:
				## The system is linked to vmware - e.g. a VM exists

				vmobj = corpus.vmware_get_vm_by_uuid(system['vmware_uuid'],system['vmware_vcenter'])

				if vmobj.runtime.powerState == vim.VirtualMachine.PowerState.poweredOn:
					actions.append({'id': 'vm.poweroff', 'desc': 'Power off the Virtual Machine', 'detail': 'UUID ' + system['vmware_uuid']})
			
				actions.append({'id': 'vm.delete', 'desc': 'Delete the virtual machine', 'detail': ' UUID ' + system['vmware_uuid']})

	## Is the system linked to service now?
	if 'cmdb_id' in system:
		if system['cmdb_id'] is not None:
			if len(system['cmdb_id']) > 0:

				if system['cmdb_is_virtual']:
					if system['cmdb_operational_status'] != u'Deleted':
						actions.append({'id': 'cmdb.update', 'desc': 'Mark the system as Deleted in the CMDB', 'detail': system['cmdb_id'] + " on " + app.config['SN_HOST']})
				else:
					if system['cmdb_operational_status'] != u'Decommissioned':
						actions.append({'id': 'cmdb.update', 'desc': 'Mark the system as Decommissioned in the CMDB', 'detail': system['cmdb_id'] + " on " + app.config['SN_HOST']})

	## Ask infoblox if a DNS host object exists for the name of the system
	try:
		refs = corpus.infoblox_get_host_refs(system['name'] + ".soton.ac.uk")

		if refs is not None:
			for ref in refs:
				actions.append({'id': 'dns.delete', 'desc': 'Delete the DNS record ', 'detail': 'Delete the name ' + system['name'] + '.soton.ac.uk - Infoblox reference: ' + ref, 'data': ref})

	except Exception as ex:
		flash("Warning - An error occured when communicating with Infoblox: " + str(type(ex)) + " - " + str(ex),"alert-warning")

	## Check if a puppet record exists
	if 'puppet_certname' in system:
		if system['puppet_certname'] is not None:
			if len(system['puppet_certname']) > 0:
				actions.append({'id': 'puppet.cortex.delete', 'desc': 'Delete the Puppet ENC configuration', 'detail': system['puppet_certname'] + ' on ' + request.url_root})
				actions.append({'id': 'puppet.master.delete', 'desc': 'Delete the system from the Puppet Master', 'detail': system['puppet_certname'] + ' on ' + app.config['PUPPET_MASTER']})

	## Check if there is an Active Directory computer object to delete
	# If systemenv is None, assume 'prod' AD domain
	if systemenv is None:
		flash("Warning - Assuming production Active Directory domain","alert-warning")
		adenv = 'prod'
	else:
		adenv = systemenv['id']

	try:
		if corpus.windows_computer_object_exists(adenv,system['name']):
			actions.append({'id': 'addelete', 'desc': 'Delete the Active Directory computer object', 'detail': system['name'] + ' on domain ' + app.config['WINRPC'][adenv]['domain']})

	except Exception as ex:
		flash("Warning - An error occured when communicating with Active Directory: " + str(type(ex)) + " - " + str(ex),"alert-warning")

	# Turn the actions list into a signed JSON document via itsdangerous
	signer = JSONWebSignatureSerializer(app.config['SECRET_KEY'])
	json_data = signer.dumps(actions)

	return render_template(__name__ + "::step2.html", actions=actions, system=system, json_data=json_data, title="Decommission Node")

@app.workflow_route("/<int:id>",methods=['GET','POST'])
@cortex.lib.user.login_required
def decom_step3(id):
	## Get the actions list 
	actions_data = request.form['actions']

	## Decode it 
	signer = JSONWebSignatureSerializer(app.config['SECRET_KEY'])
	try:
		actions = signer.loads(actions_data)
	except itsdangerous.BadSignature as ex:
		abort(400)

	return str(actions)
