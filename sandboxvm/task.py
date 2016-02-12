#### Sandbox VM Workflow Task

def run(helper, options):

	# Configuration of task
	prefix = 'play'
	vcenter_name = 'srv00080'
	domain = 'soton.ac.uk'
	puppet_cert_domain = 'soton.ac.uk'

	## Allocate a hostname #################################################

	# Start the task
	helper.event("allocate_name", "Allocating a '" + prefix + "' system name")

	# Allocate the name
	system_info = helper.lib.allocate_name(prefix, options['purpose'], helper.username)

	# system_info is a dictionary containg a single { 'hostname': database_id }. Extract both of these:
	system_name = system_info.keys()[0]
	system_dbid = system_info.values()[0]

	# End the event
	helper.end_event(description="Allocated system name " + system_name)



	## Create the virtual machine post-clone specification #################

	# Start the event
	helper.event("vm_clone", "Creating the virtual machine using VMware API")

	# For RHEL6:
	if options['template'] == 'rhel6':
		template_name = 'autotest_rhel6template'
		os_type = helper.lib.OS_TYPE_BY_NAME['Linux']
		os_name = 'Red Hat Enterprise Linux  6' # Don't delete the second space for now, ServiceNow currently needs it :(

		vm_spec = helper.lib.vmware_vm_custspec(dhcp=True, os_type=os_type, os_domain='soton.ac.uk', timezone='Europe/London')

	# For RHEL7:
	elif options['template'] == 'rhel7':
		template_name = 'RHEL7-Template'
		os_type = helper.lib.OS_TYPE_BY_NAME['Linux']
		os_name = 'Red Hat Enterprise Linux 7'

		vm_spec = helper.lib.vmware_vm_custspec(dhcp=True, os_type=os_type, os_domain='soton.ac.uk', timezone='Europe/London')

	# For Server 2012R2
	elif options['template'] == 'windows_server_2012':
		template_name = '2012R2_Template'
		os_type = helper.lib.OS_TYPE_BY_NAME['Windows']
		os_name = 'Microsoft Windows Server 2012'

		vm_spec = helper.lib.vmware_vm_custspec(dhcp=True, os_type=os_type, os_domain='devdomain.soton.ac.uk', timezone=85, domain_join_user=helper.config['AD_DEV_JOIN_USER'], domain_join_pass=helper.config['AD_DEV_JOIN_PASS'], fullname='University of Southampton', orgname='University of Southampton')

	# Anything else
	else:
		raise RuntimeError("Unknown template specified")

	# Connect to vCenter
	si = helper.lib.vmware_smartconnect(vcenter_name)

	# Launch the task to clone the virtual machine
	task = helper.lib.vmware_clone_vm(si, template_name, system_name, vm_rpool="Root Resource Pool", vm_cluster=options['cluster'], custspec=vm_spec)
	helper.lib.vmware_task_complete(task, "Failed to create the virtual machine")

	# End the event
	helper.end_event(description="Created the virtual machine successfully")

	# Get the VM object (so we can reconfigure it)
	vm = task.info.result

	# If we don't have a VM, then kill the task
	if vm == None:
		raise RuntimeError("VM creation failed: VMware API did not return a VM object reference")

	## Configure vCPUs #####################################################

	# Start the event
	helper.event("vm_reconfig_cpu", "Setting VM CPU configuration")

	# Get total CPUs desired from our options
	total_cpu = int(options['sockets']) * int(options['cores'])

	# Get number of cores per socket
	cpus_per_core = int(options['cores'])
	
	# Reconfigure the VM
	task = helper.lib.vmware_vmreconfig_cpu(vm, total_cpu, cpus_per_core)
	helper.lib.vmware_task_complete(task, "Failed to set vCPU configuration")

	# End the event
	helper.end_event(description="VM vCPU configuation saved")



	## Configure RAM #######################################################

	# Start the event
	helper.event("vm_reconfig_ram", "Setting VM RAM configuration")

	# Reconfigure the VM
	task = helper.lib.vmware_vmreconfig_ram(vm, int(options['ram']) * 1024)
	helper.lib.vmware_task_complete(task, "Failed to set RAM configuration")

	# End the event
	helper.end_event(description="VM RAM configuation saved")



	## Configure Disk ######################################################

	# Add disk to the VM
	if int(options['disk']) > 0:
		# Start the event
		helper.event("vm_add_disk", "Adding data disk to the VM")

		# Reconfigure the VM to add the disk
		task = helper.lib.vmware_vm_add_disk(vm, int(options['disk']) * 1024 * 1024 * 1024)
		helper.lib.vmware_task_complete(task, "Could not add data disk to VM")

		# End the event
		helper.end_event(description="Data disk added to VM")



	## Set up annotation ###################################################

	# Start the event
	helper.event("vm_config_notes", "Setting VM notes annotation")

	# Failure of the following does not kill the task
	try:
		# Set the notes
		task = helper.lib.vmware_vmreconfig_notes(vm, options['purpose'])

		# End the event
		helper.lib.vmware_task_complete(task, "VM notes annotation set")
	except Exception as e:
		helper.end_event(success=False, description="Failed to set VM notes annotation: " + str(e))



	## Power on the VM #####################################################

	# Start the event
	helper.event("vm_poweron", "Powering the VM on for the first time")

	# Mark the VM as not having any customisations applied, and then power on the VM
	helper.lib.vmware_task_complete(helper.lib.vmware_set_guestinfo_variable(vm, "guestinfo.cortex.customisation", "notstarted"), "Could not set VMware guestinfo variable")

	# Power on the VM
	task = helper.lib.vmware_vm_poweron(vm)
	helper.lib.vmware_task_complete(task, "Could not power on the VM")

	# If we've not powered on within 30 seconds, fail
	if not helper.lib.vmware_wait_for_poweron(vm, 30):
		helper.end_event(success=False, description="VM not powered on after 30 seconds. Check vCenter for more information")

	# End the event
	helper.end_event(description="VM powered up")	




	# Wait for VMware customisations to start
	#helper.event("vm_custom_start", "Waiting for VMware customisations to start")
	try:
	#	if helper.lib.vmware_wait_for_customisations(si, vm, desired_status=1):
	#		# If they start, mark in variable...
	#		helper.end_event(description="VMware customisations started")
	#		helper.lib.vmware_task_complete(helper.lib.vmware_set_guestinfo_variable(vm, "guestinfo.cortex.customisation", "started"), "Could not set VMware guestinfo variable")

		# ... wait for them to finish
		helper.event("vm_custom_finish", "Waiting for VMware customisations to finish")
		if helper.lib.vmware_wait_for_customisations(si, vm, desired_status=2):
			# If they finish, mark in variable...
			helper.lib.vmware_task_complete(helper.lib.vmware_set_guestinfo_variable(vm, "guestinfo.cortex.customisation", "complete"), "Could not set VMware guestinfo variable")
			helper.end_event(description="VMware customisations finished")
	except Exception, e:
		# End any open event, regardless of which one it was
		helper.end_event(success=False, description="Error occured whilst waiting for customisations: " + str(e))



	## Update Cortex Cache #################################################

	# We do this so that we don't have to wait for the next run of the 
	# scheduled VMware import).

	# Start the event
	helper.event("update_cache", "Updating Cortex VM cache item")

	# Failure of this does not kill the task
	try:
		# Update the cache item
		helper.lib.update_vm_cache(vm, vcenter_name)

		# End the event
		helper.end_event("Updated Cortex VM cache item")
	except Exception as e:
		helper.end_event(success=False, description="Failed to update Cortex VM cache item - VMware information may be incorrect")



	## Register Linux VMs with the built in Puppet ENC #####################

	# Only for Linux VMs...
	if os_type == helper.lib.OS_TYPE_BY_NAME['Linux']:
		# Start the event
		helper.event("puppet_enc_register", "Registering with Puppet ENC")

		# Register with the Puppet ENC
		helper.lib.puppet_enc_register(system_dbid, system_name + "." + puppet_cert_domain, options['env'])

		# End the event
		helper.end_event("Registered with Puppet ENC")



	## Create the ServiceNow CMDB CI #######################################

	# Start the event
	helper.event("sn_create_ci", "Creating ServiceNow CMDB CI")
	sys_id = None

	# Failure does not kill the task
	try:
		# Create the entry in ServiceNow
		(sys_id, cmdb_id) = helper.lib.servicenow_create_ci(ci_name=system_name, os_type=os_type, os_name=os_name, cpus=total_cpu, ram_mb=int(options['ram']) * 1024, disk_gb=50 + int(options['disk']), environment=options['env'], short_description=options['purpose'], comments=options['comments'], location='B54')

		# Update Cortex systems table row with the sys_id
		helper.lib.set_link_ids(system_dbid, cmdb_id=sys_id, vmware_uuid=vm.config.uuid)

		# End the event
		helper.end_event(success=True, description="Created ServiceNow CMDB CI")
	except Exception as e:
		helper.end_event(success=False, description="Failed to create ServiceNow CMDB CI")
