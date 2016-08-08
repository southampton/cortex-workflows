#!/usr/bin/python

from cortex import app
import cortex.lib.core
import cortex.lib.systems
from corpus.infoblox import CorpusInfoblox
from corpus.ad import CorpusActiveDirectory
from flask import Flask, request, session, redirect, url_for, flash, g, abort, render_template

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

				if system['vmware_guest_state'] == u'poweredOn':
					## The system is powered on
					actions.append({'id': 'vmpoweroff', 'desc': 'Power off the Virtual Machine', 'detail': 'UUID ' + system['vmware_uuid']})
			
				actions.append({'id': 'vmdelete', 'desc': 'Delete the virtual machine', 'detail': ' UUID ' + system['vmware_uuid']})

	## Is the system linked to service now?
	if 'cmdb_id' in system:
		if system['cmdb_id'] is not None:
			if len(system['cmdb_id']) > 0:

				if system['cmdb_is_virtual']:
					if system['cmdb_operational_status'] != u'Deleted':
						actions.append({'id': 'cmdbupdate', 'desc': 'Mark the system as Deleted in the CMDB', 'detail': system['cmdb_id'] + " on " + app.config['SN_HOST']})
				else:
					if system['cmdb_operational_status'] != u'Decommissioned':
						actions.append({'id': 'cmdbupdate', 'desc': 'Mark the system as Decommissioned in the CMDB', 'detail': system['cmdb_id'] + " on " + app.config['SN_HOST']})

	## Ask infoblox if a DNS host object exists for the name of the system
	try:
		ib = CorpusInfoblox(app.config)
		refs = ib.get_host_refs(system['name'] + ".soton.ac.uk")

		if refs is not None:
			for ref in refs:
				actions.append({'id': 'dnsdelete', 'desc': 'Delete the DNS record ', 'detail': 'Delete the name ' + system['name'] + '.soton.ac.uk - Infoblox reference: ' + ref, 'data': ref})

	except Exception as ex:
		flash("Warning - An error occured when communicating with Infoblox: " + str(ex),"alert-warning")

	## Check if a puppet record exists
	if 'puppet_certname' in system:
		if system['puppet_certname'] is not None:
			if len(system['puppet_certname']) > 0:
				actions.append({'id': 'puppetencdelete', 'desc': 'Delete the Puppet ENC configuration', 'detail': ''})
				actions.append({'id': 'puppetmasterdelete', 'desc': 'Delete the system from the Puppet Master', detail: ''})

	## Check if there is an Active Directory computer object to delete
	# If systemenv is None, assume 'prod' AD domain
	if systemenv is None:
		flash("Warning - Assuming production Active Directory domain","alert-warning")
		adenv = 'prod'
	else:
		adenv = systemenv['id']

	try:
		ad = CorpusActiveDirectory(app.config)

		if ad.is_computer_object(adenv,system['name']):
			actions.append({'id': 'addelete', 'desc': 'Delete the Active Directory computer object', 'detail': system['name'] + ' on domain ' + app.config['WINRPC'][adenv]['domain']})

	except Exception as ex:
		flash("Warning - An error occured when communicating with Active Directory: " + str(ex),"alert-warning")


	return render_template(__name__ + "::step2.html", actions=actions, system=system, title="Decommission Node")
