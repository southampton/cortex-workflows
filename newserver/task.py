#### Allocate server task

def run(helper, options):
	domain = "soton.ac.uk"

	## Allocate a hostname #################################################

	# Start the task
	helper.event("allocate_name", "Allocating a '" + options['classname'] + "' system name")

	# Allocate the name
	system_info = helper.lib.allocate_name(options['classname'], options['purpose'], helper.username)

	# system_info is a dictionary containg a single { 'hostname': database_id }. Extract both of these:
	system_name = system_info.keys()[0]
	system_dbid = system_info.values()[0]

	# End the event
	helper.end_event(description="Allocated system name " + system_name)



	## Allocate an IPv4 Address and create a host object ###################

	if options['alloc_ip']:
		# Start the event
		helper.event("allocate_ipaddress", "Allocating an IP address from " + options['network'])
	
		# Allocate an IP address
		ipv4addr = helper.lib.infoblox_create_host(system_name + "." + domain, options['network'])
	
		# Handle errors - this will stop the task
		if ipv4addr is None:
			raise Exception('Failed to allocate an IP address')

		# End the event
		helper.end_event(description="Allocated the IP address " + ipv4addr)
	else:
		ipv4addr = ''



	## Create the ServiceNow CMDB CI #######################################

	# Start the event
	helper.event("sn_create_ci", "Creating ServiceNow CMDB CI")
	sys_id = None
	cmdb_id = None

	if options['os_type'] == helper.lib.OS_TYPE_BY_NAME['Linux']:
		os_name = 'Other Linux'
	elif options['os_type'] == helper.lib.OS_TYPE_BY_NAME['Windows']:
		os_name = 'Not Required'
	elif options['os_type'] == helper.lib.OS_TYPE_BY_NAME['ESXi']:
		os_name = 'ESXi'
	elif options['os_type'] == helper.lib.OS_TYPE_BY_NAME['Solaris']:
		os_name = 'Solaris'

	# Failure does not kill the task
	try:
		# Create the entry in ServiceNow
		(sys_id, cmdb_id) = helper.lib.servicenow_create_ci(ci_name=system_name, os_type=options['os_type'], os_name=os_name, virtual=options['is_virtual'], environment=options['env'], short_description=options['purpose'], comments=options['comments'], ipaddr=ipv4addr)

		# Update Cortex systems table row with the sys_id
		helper.lib.set_link_ids(system_dbid, cmdb_id=sys_id, vmware_uuid=None)

		# End the event
		helper.end_event(success=True, description="Created ServiceNow CMDB CI")
	except Exception as e:
		helper.end_event(success=False, description="Failed to create ServiceNow CMDB CI")
