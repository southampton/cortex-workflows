#### Sandbox VM Workflow Task

def run(helper, options):

	# Configuration of task
	prefix = options['wfconfig']['PREFIX']
	vcenter_tag = options['wfconfig']['VCENTER_TAG']
	domain = options['wfconfig']['DOMAIN']
	puppet_cert_domain = options['wfconfig']['PUPPET_CERT_DOMAIN']

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
		os_disk_size = 50

		vm_spec = helper.lib.vmware_vm_custspec(dhcp=True, os_type=os_type, os_domain='soton.ac.uk', timezone='Europe/London')

	# For RHEL7:
	elif options['template'] == 'rhel7':
		template_name = 'RHEL7-Template'
		os_type = helper.lib.OS_TYPE_BY_NAME['Linux']
		os_name = 'Red Hat Enterprise Linux 7'
		os_disk_size = 50

		vm_spec = None #helper.lib.vmware_vm_custspec(dhcp=True, os_type=os_type, os_domain='soton.ac.uk', timezone='Europe/London')

	# For Server 2012R2
	elif options['template'] == 'windows_server_2012':
		template_name = '2012R2_Template'
		os_type = helper.lib.OS_TYPE_BY_NAME['Windows']
		os_name = 'Microsoft Windows Server 2012'
		os_disk_size = 100

		vm_spec = helper.lib.vmware_vm_custspec(dhcp=True, os_type=os_type, os_domain='devdomain.soton.ac.uk', timezone=85, domain_join_user=helper.config['AD_DEV_JOIN_USER'], domain_join_pass=helper.config['AD_DEV_JOIN_PASS'], fullname='University of Southampton', orgname='University of Southampton')

	# Anything else
	else:
		raise RuntimeError("Unknown template specified")

	# Connect to vCenter
	si = helper.lib.vmware_smartconnect(vcenter_tag)

	# Get the vm folder to use if any
	vm_folder = None
	if "default_folder" in helper.config['VMWARE'][vcenter_tag]:
		vm_folder = helper.config['VMWARE'][vcenter_tag]['default_folder']

	# Launch the task to clone the virtual machine
	task = helper.lib.vmware_clone_vm(si, template_name, system_name, vm_rpool="Root Resource Pool", vm_cluster=options['cluster'], custspec=vm_spec, vm_folder=vm_folder)
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
		helper.event("vm_add_disk", "Adding disk to the VM")

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

	# Set up the necessary values in redis
	helper.lib.redis_set_vm_data(vm, "hostname", system_name)
	helper.lib.redis_set_vm_data(vm, "ipaddress", 'dhcp')

	# Power on the VM
	task = helper.lib.vmware_vm_poweron(vm)
	helper.lib.vmware_task_complete(task, "Could not power on the VM")

	# If we've not powered on within 30 seconds, fail
	if not helper.lib.vmware_wait_for_poweron(vm, 30):
		helper.end_event(success=False, description="VM not powered on after 30 seconds. Check vCenter for more information")

	# End the event
	helper.end_event(description="VM powered up")	



	## Update Cortex Cache #################################################

	# We do this so that we don't have to wait for the next run of the 
	# scheduled VMware import).

	# Start the event
	helper.event("update_cache", "Updating Cortex VM cache item")

	# Failure of this does not kill the task
	try:
		# Update the cache item
		helper.lib.update_vm_cache(vm, vcenter_tag)

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
	cmdb_id = None

	# Failure does not kill the task
	try:
		# Create the entry in ServiceNow
		(sys_id, cmdb_id) = helper.lib.servicenow_create_ci(ci_name=system_name, os_type=os_type, os_name=os_name, cpus=total_cpu, ram_mb=int(options['ram']) * 1024, disk_gb=int(options['disk']) + os_disk_size, environment=options['env'], short_description=options['purpose'], comments=options['comments'], location='B54')

		# Update Cortex systems table row with the sys_id
		helper.lib.set_link_ids(system_dbid, cmdb_id=sys_id, vmware_uuid=vm.config.uuid)

		# End the event
		helper.end_event(success=True, description="Created ServiceNow CMDB CI")
	except Exception as e:
		helper.end_event(success=False, description="Failed to create ServiceNow CMDB CI")



	## Wait for the VM to finish building ##################################

	# Just for Linux for now...
	if os_type == helper.lib.OS_TYPE_BY_NAME['Linux']:
		# Start the event
		helper.event('guest_installer_progress', 'Waiting for in-guest installation to start')

		# Wait for the in-guest installer to set the state to 'progress' or 'done'
		wait_response = helper.lib.wait_for_guest_notify(vm, ['inprogress', 'done'])

		# When it returns, end the event
		if wait_response is None or wait_response not in ['inprogress', 'done']:
			helper.end_event(success=False, description='Timed out waiting for in-guest installation to start')

			# End the task here
			return
		else:
			helper.end_event(success=True, description='In-guest installation started')

		# Start another event
		helper.event('guest_installer_done', 'Waiting for in-guest installation to finish')

		# Wait for the in-guest installer to set the state to 'progress' or 'done'
		wait_response = helper.lib.wait_for_guest_notify(vm, ['done'])

		# When it returns, end the event
		if wait_response is None or wait_response not in ['done']:
			helper.end_event(success=False, description='Timed out waiting for in-guest installation to finish')
		else:
			helper.end_event(success=True, description='In-guest installation finished')



	## Send success email ##################################################

	if options['sendmail']:
		# Build the text of the message
		message  = 'Cortex has finished building your VM. The details of the VM can be found below.\n'
		message += '\n'
		message += 'Hostname: ' + system_name + '\n'
		message += 'IP Address: DHCP\n'
		message += 'VMware Cluster: ' + options['cluster'] + '\n'
		message += 'Purpose: ' + options['purpose'] + '\n'
		message += 'Operating System: ' + os_name + '\n'
		message += 'CPUs: ' + str(total_cpu) + '\n'
		message += 'RAM: ' + str(options['ram']) + ' GiB\n'
		message += 'Data Disk: ' + str(options['disk']) + ' GiB\n'
		message += '\n'
		message += 'The event log for the task can be found at https://cortex.dev.soton.ac.uk/task/status/' + str(helper.task_id) + '\n'
		message += 'More information about the VM, can be found on the Cortex systems page at https://cortex.dev.soton.ac.uk/systems/edit/' + str(system_dbid) + '\n'
		if sys_id is not None:
			message += 'The ServiceNow CI entry is available at ' + (helper.config['CMDB_URL_FORMAT'] % sys_id) + '\n'
		else:
			message += 'A ServiceNow CI was not created. For more information, see the task event log.\n'

		message += '\nPlease remember to move the virtual machine into an appropriate folder in vCenter\n'

		# Send the message to the user who started the task
		helper.lib.send_email(helper.username, 'Cortex has finished building your VM, ' + system_name, message)
