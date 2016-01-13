import syslog
import time

def run(helper, options):
	domain = "soton.ac.uk"
	network = "192.168.63.0/25"

	helper.event("allocate_name", "Allocating a 'play' system name")
	system_info = helper.lib.allocate_name('play', options['purpose'], helper.username)
	# system_info is a dictionary containg a single { 'hostname': database_id }. Extract both of these:
	system_name = system_info.keys()[0]
	system_dbid = system_info.values()[0]
	## ERROR HANDLING
	helper.end_event(description="Allocated system name " + system_name)

	# Allocate an IPv4 Address and Create a Host
	helper.event("allocate_ipaddress", "Allocating an IP address from " + network)
	ipv4addr = helper.lib.infoblox_create_host(system_name + "." + domain, network)
	## ERROR HANDLING
	helper.end_event(description="Allocated the IP address " + ipv4addr)

	helper.event("vm_clone", "Creating the virtual machine using VMware API")

	## Create the virtual machine post-clone specification
	if options['template'] == 'rhel6':
		template_name = 'autotest_rhel6template'
		os_type = helper.lib.OS_TYPE_BY_NAME['Linux']
		os_name = 'Red Hat Enterprise Linux  6'
		os_disk_size = 50
		vm_spec = helper.lib.vmware_vm_custspec(dhcp=False, gateway='192.168.63.126', netmask='255.255.255.128', ipaddr=ipv4addr, dns_servers=['152.78.110.110', '152.78.111.81', '152.78.111.113'], dns_domain='soton.ac.uk', os_type=os_type, os_domain='soton.ac.uk', timezone='Europe/London')
	elif options['template'] == 'windows_server_2012':
		template_name = '2012R2_Template'
		os_type = helper.lib.OS_TYPE_BY_NAME['Windows']
		os_name = 'Windows Server 2012'
		os_disk_size = 50
		vm_spec = helper.lib.vmware_vm_custspec(dhcp=False, gateway='192.168.63.126', netmask='255.255.255.128', ipaddr=ipv4addr, dns_servers=['152.78.110.110', '152.78.111.81', '152.78.111.113'], dns_domain='soton.ac.uk', os_type=os_type, os_domain='devdomain.soton.ac.uk', timezone=85, domain_join_user=helper.config['AD_DEV_JOIN_USER'], domain_join_pass=helper.config['AD_DEV_JOIN_PASS'], fullname='University of Southampton', orgname='University of Southampton')

	## Connect to vCenter
	si = helper.lib.vmware_smartconnect('srv01197')

	## Launch the task to clone the virtual machine
	task = helper.lib.vmware_clone_vm(si, template_name, system_name, vm_rpool="Root Resource Pool", vm_cluster=options['cluster'], custspec=vm_spec)
	helper.lib.vmware_task_complete(task, "Failed to create the virtual machine")
	helper.end_event(description="Created the virtual machine successfully")

	## get the VM object and reconfigure it
	vm = task.info.result

	if vm == None:
		raise Exception("VM creation failed: VMware API did not return a VM object reference")
	else:
		helper.event("vm_reconfig_cpu", "Setting VM CPU configuration")

		# Get total CPUs
		total_cpu = int(options['cpu'])

		# Choose how many cores per CPU (we disallow some configurations). TODO: Fix this
		core_cpu_map = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, None, 4]
		cpus_per_core = core_cpu_map[total_cpu]
		if cpus_per_core is None:
			raise Exception('Invalid number of vCPUs')
		
		## Configure VM CPUs
		task = helper.lib.vmware_vmreconfig_cpu(vm, total_cpu, cpus_per_core)
		helper.lib.vmware_task_complete(task, "Failed to set vCPU configuration")
		helper.end_event(description="VM vCPU configuation saved")

		# Configure VM RAM
		helper.event("vm_reconfig_ram", "Setting VM RAM configuration")
		task = helper.lib.vmware_vmreconfig_ram(vm, int(options['ram']) * 1024)
		helper.lib.vmware_task_complete(task, "Failed to set RAM configuration")
		helper.end_event(description="VM RAM configuation saved")

		# Add disk to the VM
		if int(options['disk']) > 0:
			helper.event("vm_add_disk", "Adding data disk to the VM")
			task = helper.lib.vmware_vm_add_disk(vm, (int(options['disk']) - os_disk_size) * 1024 * 1024 * 1024)
			helper.lib.vmware_task_complete(task, "Could not add data disk to VM")
			helper.end_event(description="Data disk added to VM")

		# Power on the VM
		helper.event("vm_poweron", "Powering the VM on for the first time")
		task = helper.lib.vmware_vm_poweron(vm)
		helper.lib.vmware_task_complete(task, "Could not power on the VM")
		if not helper.lib.vmware_wait_for_poweron(vm, 30):
			helper.lib.end_event(success=False, description="VM not powered on after 30 seconds. Check vCenter for more information")
		helper.end_event(description="VM powered up")	

		# Update VMware cache item (so we don't have to wait for the next run 
		# of the scheduled VMware import)
		helper.event("update_cache", "Updating Cortex VM cache item")
		try:
			helper.lib.update_vm_cache(vm, 'srv00080')
			helper.end_event("Updated Cortex VM cache item")
		except Exception as e:
			helper.end_event(success=False, "Failed to update Cortex VM cache item - VMware information may be incorrect")

		# Automatically register Linux VMs with the built in Puppet ENC
		if os_type == helper.lib.OS_TYPE_BY_NAME['Linux']:
			helper.event("puppet_enc_register", "Registering with Puppet ENC")
			helper.lib.puppet_enc_register(system_dbid, system_name + ".soton.ac.uk", "production")
			helper.end_event("Registered with Puppet ENC")

		# Create the ServiceNow CMDB CI
		helper.event("sn_create_ci", "Creating ServiceNow CMDB CI")
		try:
			# Create the entry in ServiceNow
			(sys_id, cmdb_id) = helper.lib.servicenow_create_ci(ci_name=system_name, os_type=os_type, os_name=os_name, cpus=total_cpu, ram_mb=int(options['ram']) * 1024, disk_gb=int(options['disk']), environment=options['env'], short_description=options['purpose'], comments=options['comments'], location='Astro House', ipaddr=ipv4addr)
			# Update Cortex systems table row with the sys_id
			helper.lib.set_link_ids(system_dbid, sys_id)
			helper.end_event(success=True, description="Created ServiceNow CMDB CI")
		except Exception as e:
			helper.end_event(success=False, description="Failed to create ServiceNow CMDB CI")
			raise(e)
	
