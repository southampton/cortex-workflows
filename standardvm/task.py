import syslog
import time

def run(helper, options):
	domain = "soton.ac.uk"
	network = "192.168.63.0/25"

	helper.event("allocate_name", "Allocating a 'play' system name")
	system_info = helper.lib.allocate_name('play', 'Automatic VM', helper.username)
	system_name = system_info.keys()[0]
	## ERROR HANDLING
	helper.end_event(description="Allocated system name " + system_name)

	# Allocate an IPv4 Address and Create a Host
	helper.event("allocate_ipaddress", "Allocating an IP address from " + network)
	ipv4addr = helper.lib.infoblox_create_host(system_name + "." + domain, network)
	## ERROR HANDLING
	helper.end_event(description="Allocated the IP address " + ipv4addr)

#	print ipv4addr

#	if ipv4addr is None:
#		abort(500)

	#cortex.core.vmware_clone_vm('2012r2template',system_name, cortex.core.OS_TYPE_BY_NAME['Windows'], ipv4addr, "192.168.63.126", "255.255.255.128")

	helper.event("vm_clone", "Creating the virtual machine using VMware API")

	## Create the virtual machine post-clone specification
	if options['template'] == 'linux':
		template_name = 'autotest_rhel6template'
		os_type = helper.lib.OS_TYPE_BY_NAME['Linux']
		os_name = 'Red Hat Enterprise Linux 6'
		vm_spec = helper.lib.vmware_vm_custspec(dhcp=False, gateway = '192.168.63.126', netmask = '255.255.255.128', ipaddr = ipv4addr, dns_servers = ['152.78.110.110','152.78.111.81', '152.78.111.113'], dns_domain = 'soton.ac.uk', os_type = os_type, os_domain = 'soton.ac.uk', timezone = 'Europe/London')
	else:
		template_name = '2012R2_Template'
		os_type = helper.lib.OS_TYPE_BY_NAME['Windows']
		os_name = 'Windows Server 2012'
		vm_spec = helper.lib.vmware_vm_custspec(dhcp=False, gateway = '192.168.63.126', netmask = '255.255.255.128', ipaddr = ipv4addr, dns_servers = ['152.78.110.110','152.78.111.81', '152.78.111.113'], dns_domain = 'soton.ac.uk', os_type = os_type, os_domain = 'devdomain.soton.ac.uk', timezone = 85, domain_join_user = helper.config['AD_DEV_JOIN_USER'], domain_join_pass = helper.config['AD_DEV_JOIN_PASS'], fullname = 'University of Southampton', orgname = 'University of Southampton')

	## connect to vcenter
	si = helper.lib.vmware_smartconnect('srv00080')

	## Launch the task to clone the virtual machine
	task = helper.lib.vmware_clone_vm(si, template_name, system_name, vm_rpool="Root Resource Pool", custspec=vm_spec)

	## Wait for the task to complete
	result = helper.lib.vmware_task_wait(task)
	if result == False:
		if hasattr(task.info.error,'msg'):
			error_message = task.info.error.msg
		else:
			error_message = str(task.info.error)
		helper.end_event(success=False,description="Failed to create the virtual machine: " + error_message)
		raise Exception("VM creation failed: Failed to clone the virtual machine template")
	else:
		helper.end_event(success=True,description="Created the virtual machine successfully")
	
	## get the VM object and reconfigure it
	vm = task.info.result

	if vm == None:
		raise Exception("VM creation failed: VMware API did not return a VM object reference")
	else:
		helper.event("vm_reconfig_cpu", "Setting VM CPU configuration")

		if int(options['cpu']) == 1:
			total_cpu = 1
			cpus_per_core = 1
		elif int(options['cpu']) == 2:
			total_cpu = 2
			cpus_per_core = 2
		elif int(options['cpu']) == 4:
			total_cpu = 4
			cpus_per_core = 2
		elif int(options['cpu']) == 8:
			total_cpu = 8
			cpus_per_core = 4

		## Configure VM CPUs
		task = helper.lib.vmware_vmreconfig_cpu(vm, total_cpu, cpus_per_core)
		result = helper.lib.vmware_task_wait(task)
		if result == False:
			if hasattr(task.info.error, 'msg'):
				error_message = task.info.error.msg
			else:
				error_message = str(task.info.error)
			helper.end_event(success=False, description="Failed to set vCPU configuration: " + error_message)
			raise Exception("VM creation failed: Failed to set vCPU configuration")
		else:
			helper.end_event(success=True, description="VM vCPU configuation saved")

		# Configure VM RAM
		helper.event("vm_reconfig_ram", "Setting VM RAM configuration")
		task = helper.lib.vmware_vmreconfig_ram(vm, int(options['ram']) * 1024)
		result = helper.lib.vmware_task_wait(task)
		if result == False:
			if hasattr(task.info.error,'msg'):
				error_message = task.info.error.msg
			else:
				error_message = str(task.info.error)
			helper.end_event(success=False, description="Failed to set VM RAM configuration: " + error_message)
			raise Exception("VM creation failed: Failed to set VM RAM configuration")
		else:
			helper.end_event(success=True, description="VM RAM configuation saved")

		# Add disk to the VM
		helper.event("vm_add_disk", "Adding data disk to the VM")
		task = helper.lib.vmware_vm_add_disk(vm, int(options['disk']) * 1024 * 1024 * 1024)
		result = helper.lib.vmware_task_wait(task)
		if result == False:
			if hasattr(task.info.error,'msg'):
				error_message = task.info.error.msg
			else:
				error_message = str(task.info.error)
			#print task.info.error
			helper.end_event(success=False, description="Failed to add second disk: " + error_message)
			raise Exception("VM creation failed: Failed to add second disk")
		else:
			helper.end_event(success=True, description="Data disk added to VM")

		# Power on the VM
		helper.event("vm_poweron", "Powering the VM on for the first time")
		task = helper.lib.vmware_vm_poweron(vm)
		result = helper.lib.vmware_task_wait(task)
		if result == False:
			if hasattr(task.info.error,'msg'):
				error_message = task.info.error.msg
			else:
				error_message = str(task.info.error)
			helper.end_event(success=False, description="Failed to power on the VM: " + error_message)
			raise Exception("VM creation failed: Failed to power on the VM")
		else:
			helper.end_event(success=True, description="VM powered up")	

		# Create the ServiceNow CMDB CI (disabled for now)
		#helper.event("sn_create_ci", "Creating ServiceNow CMDB CI")
		#try:
		#	sys_id = helper.lib.servicenow_create_ci(ci_name=system_name, os_type=os_type, os_name=os_name, cpus=total_cpu, ram_mb=int(options['ram']), disk_gb=50 + int(options['disk']), ipaddr=ipv4addr)
		#	helper.end_event(success=True, description="Created ServiceNow CMDB CI")
		#	# TODO: Update Cortex entry to include sys_id
		#except Exception as e:
		#	helper.end_event(success=False, description="Failed to create ServiceNow CMDB CI")
		#	raise(e)
		
