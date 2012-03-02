#!/usr/bin/python
# Copyright (c) 2009 Stephen Childs, and
# Trinity College Dublin.
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#
# Modified by: Marcus Breese <mbreese@iupui.edu>
#			  2011-02-08
#			  for pbs_python version 4.1.0
#
#

from PBSQuery import PBSQuery, PBSError
from getopt import getopt
import sys
import datetime
from time import strftime
import os,urllib
import re

import cgitb; cgitb.enable()
import cgi
# get options from config file
import ConfigParser


# Input variables
NODE_STATES=['down','free','job-exclusive','offline','busy','down,offline','down,job-exclusive','state-unknown','down,busy','job-exclusive,busy']
JOB_STATES=['R','Q','E','C','H','W','T']
JOB_EFFIC={}
USER_EFFIC={} # Dict containing all users and associated jobs
CONFIG_FILE="/etc/pbswebmon.conf"
njobs=-1
users={}

def header(checkboxes):
	""" Print the header of the HTML page.
	The parameter REFRESH_TIME is globaly defined.
	\param checkboxes State of the checkboxes.
	"""
	if checkboxes['refresh'] == 1:
		str_refresh = '''<meta http-equiv="refresh" content="%s">''' % (REFRESH_TIME)
	else:
		str_refresh = ''''''
	
	print '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
	%s
	<title>PBSWebMon</title> 
	<script src="/pbswebmon/js/table.js" type="text/javascript"></script>
	<script src="/pbswebmon/js/datasel.js" type="text/javascript"></script>
	<script type="text/javascript">
		var iTimeout;
		function set_refresh(refresh) {
			if (refresh) {
				if (window.setTimeout) {
					iTimeout = window.setTimeout('if (location.reload) location.reload();', %s*1000);
				}
			} else {
				if (window.clearTimeout) window.clearTimeout(iTimeout);
			}
		}
		/* JQuery
		$(function () {
			$('form *').autosave();
		}); */
	</script>
	<link rel="stylesheet" type="text/css" href="/pbswebmon/css/table.css" media="all" />
	<link rel="stylesheet" type="text/css" href="/pbswebmon/css/local.css" media="all" />
</head>''' % (str_refresh, REFRESH_TIME)

#def build_addr(address, opt, key):
	#""" Build the address according to the state needed to be changed
	#\param address The basename address
	#\param opt The options to be added
	#\param key The key which is going to be changed
	#\return address_opt The address which will be reloaded
	#"""
	
	#address_opt = address+"?"
	#i = 0
	#for str_lst in opt.keys():
		#if key == str_lst:
			#if opt[str_lst] == "yes":
				#opt2 = "no"
			#else:
				#opt2 = "yes"
		#else:
			#opt2 = opt[str_lst]
		
		#i += 1
		#if i == len(opt):
			#address_opt += str_lst+"="+opt2 # last parameter to be added
		#else:
			#address_opt += str_lst+"="+opt2+"&"
	
	#if True:
		#print "<!-- DEBUG address_opt: ",key, address_opt,"-->"
	
	#return address_opt

def print_summary(script, param_check, checkboxes):
	""" Print the Summary cluster status
	\param script The script URL.
	\param param_check The parameters in the URL.
	\param checkboxes State of the checkboxes.
	"""
	address = script[8:] # this needs to be optimized!
	if DEBUG:
		print "<!-- DEBUG address: ",address,"-->"
		print "<!-- DEBUG param_check: ",len(param_check.list),"-->"
		print "<!-- DEBUG param_check: ",param_check.keys(),"-->"
	
	str_check = {}
	str_refresh = {}
	
	# Get the checkbox state for each checkbox
	for lst_checkbox in checkboxes.iterkeys():
		if DEBUG:
			print "<!-- DEBUG lst_checkbox: ", lst_checkbox,"-->"
		if checkboxes[lst_checkbox] == 1:
			str_refresh[lst_checkbox] = "yes"
			str_check[lst_checkbox] = '''checked="checked"'''
		else:
			str_refresh[lst_checkbox] = "no"
			str_check[lst_checkbox] = ''''''
	
	print "<!-- print_summary -->"
	print "<div class='summary_box'>"
	print '''	<table class='summary_box_table'>
		<tr class='summary_box_entry'>
			<td>
				<b>Cluster status</b><br/>
				%s<br />
				Refreshes every %s seconds. <br />''' % (strftime("%Y-%m-%d %H:%M:%S"), REFRESH_TIME)
	print '''				<form class="showdetails" action="/cgi-bin/pbswebmon.py">
					<p>'''
	
	# Build all checkboxes
	#addr = build_addr(address, str_refresh, 'node')
	print '''						<input type="checkbox" id="show_node_grid" name="show_node_grid" %s onclick="show_hide_data(\'node_grid\',!this.checked,false);" />Hide node list<br />''' % (str_check['node'])
	#addr = build_addr(address, str_refresh, 'job')
	print '''						<input type="checkbox" id="showdetails" name="showdetails" %s onclick="show_hide_data(\'jobdata\', !this.checked, false);" />Hide all job details<br />''' % (str_check['job'])
	#addr = build_addr(address, str_refresh, 'header')
	print '''						<input type="checkbox" id="fixed_header" name="Fixed header" %s onclick="on_top(\'summary_box\', !this.checked);" />Do not fix header on top<br />''' % (str_check['header'])
	#addr = build_addr(address, str_refresh, 'refresh')
	print '''						<input type="checkbox" id="refresh" name="refresh" %s />Auto-refresh
					</p>
				</form>
			</td>''' % (str_check['refresh'])

def user_effic(user):
	""" Efficiency for the running user
	\param user The string for the user to be parsed
	\return effic The calculated efficiency (type float)
	"""
	effic = 0.0
	if USER_EFFIC.has_key(user):
		for job in USER_EFFIC[user]:
			effic += job
			if DEBUG:
				print "<!-- DEBUG effic job: ",job,"-->"
		effic = (effic / float(len(USER_EFFIC[user]))*100.0)
		#effic /= float(len(USER_EFFIC[user]))*100.0
		if DEBUG:
			print "<!-- DEBUG effic: ",effic,"-->"

	return effic
		

def job_effic(myjob):
	""" Efficiency for the job
	\param myjob The job to be parsed
	\return effic The calculated job efficiency
	"""
	effic = 0.0
	walltime = 0.0
	if 'resources_used' in myjob:
		if 'cput' in myjob['resources_used']:
			cput = convert_time(myjob['resources_used']['cput'][0])
		if 'walltime' in myjob['resources_used']:
			walltime = convert_time(myjob['resources_used']['walltime'][0])		
		
	if walltime != 0.0:
		effic = float(cput)/float(walltime)

	return effic

def get_poolmapping(gridmapdir):
	""" ???
	\todo Understand this function...
	"""

	# find files with more than one link in current directory
	allfiles=os.listdir(gridmapdir)

	maptable=dict()
	inodes=dict()

	# sort the list so the "dn-files" come first
	allfiles.sort()

	for file in allfiles:
		statinfo=os.stat(os.path.join(gridmapdir,file))

		if (file[0] == '%'):
			inodes[statinfo.st_ino]=urllib.unquote(file)
		else:
			if (statinfo.st_nlink == 2):
				maptable[file]=inodes[statinfo.st_ino]

	return maptable

def get_dn (ownershort):
	""" ???
	\param ownershort The short name for the user
	\todo Understand this function...
	\return ownerdn The username
	"""
	# user info
	if ownershort in userdnmap:
		ownerdn = userdnmap[ownershort]
	else:
		ownerdn = ownershort

	if DEBUG:
		print "<!-- DEBUG ownerdn: ",ownerdn,"-->"
		print "<!-- DEBUG userdnmap: ",userdnmap,"-->"
	return ownerdn

def convert_time (timestr):
	""" Convert time into seconds
	\param timestr The time in HH:MM:SS
	\return seconds The time in seconds
	"""
	hours,mins,secs=timestr.split(':')

	seconds=(60*60*int(hours))+(60*int(mins))+int(secs)
	return seconds
	
def convert_to_gb (kbmem):
	""" Convert kilobytes or megabytes of memory to gigabytes
	\param kbmem The amount of memory in kB or MB
	\return mem The amount of memory in GB
	"""
	idx = kbmem.rfind("kb")
	if (idx != -1):
		mem = float(kbmem[0:idx])/(1000.0*1000.0)
		return mem

	idx = kbmem.rfind("mb")
	if (idx != -1):
		mem = float(kbmem[0:idx])/(1000.0)
		mem = float(kbmem[0:idx])/(1000.0)
		return mem

def fill_user_list (jobs):
	""" ???
	\todo Understand this function...
	"""
	for name, atts in jobs.items():
		if 'job_state' in atts:
			job_type = atts['job_state'][0]
		ownershort = atts['Job_Owner'][0].split('@')[0]
		effic = job_effic(atts)
		if not ownershort in USER_EFFIC:
			USER_EFFIC[ownershort] = []
		USER_EFFIC[ownershort].append(effic)
		if not ownershort in users:
			users[ownershort] = {}
			users[ownershort]['jobs'] = 1
			for state in JOB_STATES:
				if state == job_type:
					users[ownershort][state] = 1
				else:
					users[ownershort][state] = 0
		else:
			users[ownershort]['jobs'] += 1
			users[ownershort][job_type] += 1
	return users
		   
def print_user_summary(users):
	""" Prints the users summary
	\param users The user list
	"""
	print '''				<table class='example table-sorted-desc table-autosort:1 table-stripeclass:alternate user_summary' >
					<caption>Users</caption>
					<thead><tr>
						<th class='table-filterable table-sortable:default' align='left'>User</th>'''
	totals={}

	for state in JOB_STATES:
		print "						<th class='table-filterable table-sorted-desc table-sortable:numeric'>%s</th>" % state
		totals[state]=0
	print "						<th class='table-sortable:numeric'>Efficiency</th>"
	print "					</tr></thead>"

	total = 0
	tot_effic = 0.0
	tbodytmp = '''					<tbody>'''
	for user, atts in users.items():
		njobs = '0'
		if 'jobs' in atts.keys():
			njobs = atts['jobs']
			total += njobs
			
			tbodytmp += '''<tr>
						<td onmouseover='highlight(\"%s\")' onmouseout='dehighlight(\"%s\")'title='%s'>%s</td>\n''' % (user,user,get_dn(user),user)
			for state in JOB_STATES:
				tbodytmp += "						<td>%d</td>\n" % atts[state]
				totals[state] += atts[state]
			tmp_effic = user_effic(user)
			tbodytmp += "						<td>%.0f</td>\n" % tmp_effic
			tot_effic += tmp_effic
			del tmp_effic
			tbodytmp += "					</tr>"
	tbodytmp += '''</tbody>'''

	print '''					<tfoot><tr>
						<td><b>Total</b></td>'''
	for state in JOB_STATES:
		print "						<td><b>%s</b></td>" % totals[state]
	print "						<td><b>%.0f</b></td>" %tot_effic
	print "					</tr></tfoot>"
	print tbodytmp
	del tbodytmp
	print "				</table>"
	
def print_node_summary(nodes):
	""" Print summary of all nodes information as a table.
	By default this will display the states:
	- down: number of nodes down
	- offline: number of nodes offline
	- state-unknown: number of nodes with an unknown state
	- job-exclusive: number of nodes which are reserved for jobs
	- free: number of free nodes
	- Total: all the nodes
	\param nodes The nodes...
	"""
	print "				<table class='example table-sorted-desc table-autosort:1 node_summary'>"
	print "					<caption>Nodes</caption>"
	print "					<thead><tr>"

	totals = {}

	print "						<th class='table-filterable table-sortable:default' align='left'>State</th>"
	print "						<th class='table-filterable table-sorted-desc table-sortable:numeric'>Count</th>"
	for s in NODE_STATES:
		totals[s] = 0

	print "					</tr></thead>"
	for name, node in nodes.items():
		if 'state' in node.keys():
			totals[node['state'][0]] += 1

	total = 0
	tbodytmp = "					<tbody>"
	for s in NODE_STATES:
		tdclass = s
		if (s == "down,job-exclusive"):
			tdclass="down"
		tbodytmp += '''<tr>
						<td class='%s'>%s</td>
						<td class='%s'>%d</td>
					</tr>''' %(tdclass,s,tdclass,totals[s])
		total += totals[s]
	tbodytmp += "</tbody>"
	print '''					<tfoot><tr>
						<td><b>Total</b></td>
						<td>%d</td>
					</tr></tfoot>''' %total
	print tbodytmp
	del tbodytmp
	print "				</table>"


def print_queue_summary(queues):
	""" Print the queue summary table
	"""
	print '''				<table class='example table-sorted-desc table-autosort:1 table-stripeclass:alternate queue_summary'>
					<caption>Queues</caption>
					<thead><tr>'''
	
	headers = ['Running','Queued','Held']
	print "						<th class='table-filterable table-sortable:default' align='left'>Name</th>"
	
	totals={}
	for h in headers:
		totals[h] = 0
	
	for header in headers:
		print "						<th class='table-filterable table-sortable:numeric'>",header,"</th>"
	print "					</tr></thead>"
	
	tbodytmp = "					<tbody>\n"
	for queue, atts in queues.items():
		tbodytmp += "					<tr>\n"
		tbodytmp +=  "						<td>"+"".join(queue)+"</td>\n" # join because queue is a tuple

		state = atts['state_count'][0]
		state_counts = state.split()
		statedict = {}
		for entry in state_counts:
			type,count=entry.split(":")
			statedict[type] = count


		for s in headers:
			tbodytmp += "						<td align='right'>"+"".join(statedict[s])+"</td>\n" # join because statedict is a tuple
			totals[s] += int(statedict[s])
			
		tbodytmp += "					</tr>\n"
		
	tbodytmp += "					</tbody>"
	print '''					<tfoot><tr>
						<td><b>Total</b></td>'''
	for h in headers:
		print "						<td align='right'><b>%d</b></td> " %(totals[h])
	print "					</tr></tfoot>"
	print tbodytmp
	del tbodytmp
	print "				</table>"

def print_key_table():
	""" This function is yet unused...
	"""

	print "<table class='key_table'>"
	print "<tr><th>Node color codes</th></tr>"
	allstates = NODE_STATES[:]
	allstates.append('partfull')
	for s in allstates:
		print "<tr><td class='%s'>%s</td></tr>" %(s,s)

	print "</table>"

def print_lame_list(nodelist, nodes):
	""" Show list of of all the lame
	\param nodelist The list of all nodes (unsorted)
	\param nodes The nodes information
	"""
	print '''	<table class=\"node_grid\">
		<tr>'''
	count = 0
	def nsort(l):
		""" Sort lames by number
		\param l The list of the lames
		\return The list of the lames in a sorted way
		"""
		ret = []
		for el in l:
			# Split each node in a dict of letter and figures
			r = re.compile(r"([a-z\s]+)(\d+)",re.IGNORECASE)
			matchs = r.match(el)
			# match.groups()[0]: letters
			# match.groups()[1]: figures
			ret.append((int(matchs.groups()[1]),el))
		ret.sort()
		return [x[1] for x in ret]
	
	# Sort lame in the order
	nodelist = nsort(nodelist)
	if DEBUG:
		print "<!-- DEBUG nodelist: ",nodelist,"-->"
		print "<!-- DEBUG nodes: ",nodes,"-->"

	for name in nodelist:
		if DEBUG:
			print "<!-- DEBUG name: ",name,"-->"
		if name in nodes:
			node = nodes[name]
			attdict={}
			if 'status' in node.keys():
				attdict = node['status']
			
		if node.has_key('state'):
			node_state = node['state'][0]
			if DEBUG:
				print "<!-- DEBUG node_state: ",node_state ,"-->"

			if node.has_key('jobs'):
				myjobs = node['jobs']
				if DEBUG:
					print "<!-- DEBUG myjobs:",myjobs,"-->"
			else:
				myjobs = []

			# get the number of users
			nusers = '0' # this is a string!
			if attdict.has_key('nusers'):
				nusers = attdict['nusers'][0]
				if DEBUG:
					print "<!-- DEBUG nusers:",nusers,"-->"

			# get the physical memory and convert to GB
			physmem = 0.0
			if attdict.has_key('physmem'):
				physmem = convert_to_gb(attdict['physmem'][0])	
				if DEBUG:
					print "<!-- DEBUG physmem:",physmem,"-->"		
			
			# Get the Load Average
			loadave = "n/a"
			if attdict.has_key('loadave'):
				loadave = attdict['loadave'][0]
				if DEBUG:
					print "<!-- DEBUG loadave:",loadave,"-->"	
			
			if (node_state == 'free' and (len(myjobs) > 0)):
				node_state = 'partfull'
			if (node_state == 'down,job-exclusive'):
				node_state = 'down'
			print "			<td valign='top'>"
			print '''				<form class="%s" action="/cgi-bin/pbswebmon.py">
					<p><b>%s<input class="job_indiv" type="checkbox" name="showdetails" checked="checked" onclick="show_hide_data_id('%s', this.checked)" />Show jobs</b><br />''' % (node_state,name, name)
			print '''					%d jobs, %s users, %.2f GB, %s load</p>
				</form>''' % (len(myjobs),nusers,physmem,loadave)
			print "				<span class='jobdata' id='"+name+"' style='display:block'>"
			
			for myjobstr in myjobs:
				myjobstr = myjobstr.lstrip()
				cpu,jid = myjobstr.split('/')
				jidshort = jid.split('.')[0]
				myjob = jobs[jid]
				ownershort = myjob['Job_Owner'][0].split('@')[0]
				if not ownershort in users:
					users[ownershort] = {}
					users[ownershort]['jobs'] = 1
				else:
					users[ownershort]['jobs'] += 1
				mem = 0.0
				memreq = 0.0
				cput = 0
				walltime = 1
				effic = 0
				if DEBUG:
					print "<!-- DEBUG myjob.keys:",myjob.keys(),"-->"
					print "<!-- DEBUG myjob['Resource_List']:",myjob['Resource_List'],"-->"
					print "<!-- DEBUG myjob['resources_used']['mem']:",type(myjob['resources_used']['mem'][0]),"-->"
					print "<!-- DEBUG myjob['Walltime']['Remaining'][0]:",myjob['Walltime']['Remaining'][0],"-->"
				if myjob.has_key('resources_used'):
					mem = convert_to_gb(myjob['resources_used']['mem'][0])
					if DEBUG:
						print "<!-- DEBUG mem:",mem,"-->"
				if  myjob['Resource_List'].has_key('mem'):
					memreq = convert_to_gb(myjob['Resource_List']['mem'][0])

				if myjob['Resource_List'].has_key('walltime'):
					walltime = convert_time(myjob['Resource_List']['walltime'][0])
					if DEBUG:
						print "<!-- DEBUG walltime:",walltime,"-->"	

				try:
					if myjob['Walltime'].has_key('Remaining'):
						# cput = walltime - remaining
						cput = int(walltime) - int(myjob['Walltime']['Remaining'][0])
						if DEBUG:
							print "<!-- DEBUG cput:",cput,"-->"	
				except:
					cput = 0
					
				if myjob.has_key('queue'):
					myqueue = myjob['queue'][0]

				if walltime != 0:
					effic = float(cput)/float(walltime)
					if DEBUG:
						print "<!-- DEBUG effic:",effic,"-->"	

				wrap=" "
				print "					<span title='"+jidshort+": "+myqueue+"'>"+cpu+ ": "+jidshort+ "</span>"

				# user info
				ownerdn = get_dn(ownershort)
					
				print "					<span style=\"white-space: pre;\" title='%s'> %-10s</span>" %(ownerdn,ownershort[0:len(ownershort)])
				print "					<span style=\"white-space: pre;\" title='%s/%s s'>" % (cput, walltime),
				if effic < .8:
					print "<span style='text-color: gray;'>",
				else:
					if effic > 1.0:
						print "<span style='text-color: red;'>",
					else:
						print "<span style='text-color: black;'>",
						
				print "%7.2f%%\t</span> " % (effic*100.0),
				print "</span>"
				
				# Try and except to test if the user has defined mem in script
				try:
					if (mem > memreq and memreq > 0.0):
						print "					<span style='text-color: red;'>",
					else:
						if mem < 0.5*memreq:
							print "					<span style='text-color: gray;'>",
						else:
							print "					<span style='text-color: black;'>",

				except:
					memreq = 0.0
					print "					<span style='text-color: blue;'>",
				

				print "%.2f/%.2f GB</span>" %(mem,memreq),
				print "<br />\n"
			print "				</span> <!-- class='jobdata' -->"
			print "			</td>"
			if (count and ((count%GRID_COLS)) == GRID_COLS-1):
				if DEBUG:
					print "<!-- ",count,"!-->\n"
				if count == len(nodelist)-1:
					print "		</tr>\n\n"
				else:
					print "		</tr>\n\t\t<tr>\n"
			count += 1
	
	#print "	</table> <!-- class=\" table-autosort:0 node_grid\" -->"
	print "	</table> <!-- class=\"node_grid\" -->"


def print_job_list():
	""" Print the job list. Yet it shows:
	- The Job ID
	- The username
	- The queue
	- The nodes (when the job is running)
	- The number of cores asked
	- The state of the job
	- The elapsed time
	- The walltime
	"""
	print
	print "<!-- Job List -->"
	print "	<table class='example table-sorted-asc table-autosort:0 joblist'>"
	print "		<caption>Jobs<br /></caption>"
	
	print "		<thead><tr>"
	print "			<th class='table-sortable:default'>Job ID</th>"
	print "			<th class='table-sortable:default'>Username</th>"
	print "			<th class='table-sortable:default'>Queue</th>"
	print "			<th class='table-sortable:default'>Jobname</th>"
	print "			<th class='table-sortable:numeric'>Nodes</th>"
	print "			<th class='table-sortable:numeric'>Lame</th>"
	print "			<th class='table-sortable:numeric'>Cores</th>"
	print "			<th class='table-sortable:default'>State</th>"
	print "			<th class='table-sortable:numeric'>Elapsed Time</th>"
	print "			<th class='table-sortable:numeric'>Walltime</th>"
	print "		</tr></thead>"
	print "		<tbody>"
		
	for name,job in jobs.items():
		owner = job['Job_Owner'][0]
		if DEBUG:
			print "<!-- DEBUG owner.split: ",owner.split('@')[0],"-->"
			print "<!-- DEBUG job: ",job,"-->"
		
		# Get exec lame, number of cores, number of nodes
		if job['job_state'][0] == 'R':
			exec_host = job['exec_host'][0]
			exec_host = exec_host.split('+')
			# Add a first fictive element in all_hosts and all_cpu
			all_hosts =  ['a']
			all_cpu= ['a']
			for ele in range(len(exec_host)):
				host,cpu = exec_host[ele].split('/')
				host = re.sub('[a-zA-Z]*', '', host) # Remove all letters from the host
				if DEBUG:
					print "<!-- DEBUG re.sub('[a-zA-Z]*', '', host): ",re.sub('[a-zA-Z]*', '', host),"-->"
				if DEBUG:
					print "<!-- DEBUG len(exec_host): ",len(exec_host),"-->"
				for all_ele in 0 or range(len(all_hosts)):
					if not (host in all_hosts):
						all_hosts.append(host)
			# Remove first ficitive element
			all_hosts.pop(0)
			if DEBUG:
				print "<!-- DEBUG all_hosts: ",all_hosts,"-->"
		print "			<tr>"
		print "				<td class=\"JOBID\">",name.split('.')[0],"</td>" # The JOB ID
		print "				<td class=\"username\">",owner.split('@')[0],"</td>" # The username
		print "				<td class=\"queue\">",job['queue'][0],"</td>" # The queue
		print "				<td class=\"jobname\">",job['Job_Name'][0],"</td>" # The jobname
		if job['Resource_List'].has_key('nodect'):
			print "				<td class=\"nodes\">"+job['Resource_List']['nodect'][0]+"</td>" # The number of nodes asked
		if job['job_state'][0] == 'R':
			str_hosts = ", ".join(all_hosts) # Join the all_hosts list in one string separated with comma
			if DEBUG:
				print "<!-- DEBUG str_hosts: ",str_hosts,"-->"
			print "				<td class=\"lames\">"+str_hosts+"</td>" # The running lame
		else:
			print "				<td class=\"lames\"></td>" # The jobs is not running so no lame to print
		try:
			print "				<td class=\"cores\">",job['Resource_List']['nodes'][0].split('=')[1],"</td>" # The number of cores
		except:
			print "				<td class=\"cores\" style=\"text-color: red;\"> -- </td>"
		print "				<td class=\"state\">",job['job_state'][0],"</td>" # The job state
		try:
			if job['job_state'][0] == 'R' and job['resources_used'].has_key('walltime'):
				print "				<td class=\"elapsed_time\">",job['resources_used']['walltime'][0],"</td>" # Get the time elapsed
			else:
				print "				<td class=\"elapsed_time\"></td>" # When the job is not running it raises an exception as job['resources_used']['walltime'] is not available. So print nothing
		except:
			print "				<td class=\"elapsed_time\" style=\"text-color: red;\"> -- </td>" # When the job is not running it raises an exception as job['resources_used']['walltime'] is not available. So print nothing
		
		try:
			if job['Resource_List'].has_key('walltime'):
				print "				<td class=\"walltime\">",job['Resource_List']['walltime'][0],"</td>" # Get the walltime
			else:
				print "				<td class=\"walltime\"></td>"
		except:
			print "				<td class=\"walltime\" style=\"text-color: red;\"> -- </td>"
			
		print "			</tr>"
	
	print "		</tbody>\n\t</table>"

######################
# Start of pbswebmon #
######################

# get command line options (unused now?)
optlist, args=getopt(sys.argv[1:], 'j:')
nodelist=[]
for arg in args:
	nodelist.append(arg)

for o,a in optlist:
	if o == '-j':
		njobs=int(a)
		
try:
	config=ConfigParser.RawConfigParser({'name':None, 'translate_dns':'no', 'gridmap': '/etc/grid-security/gridmapdir'})
	config.readfp(open(CONFIG_FILE))
	serveropts=config.items('server')
	gridopts= config.items('grid')
except:
	print "Error reading config"
	sys.exit(1)

# Get options from [server] in /etc/pbswebmon.conf
DEBUG = False
REFRESH_TIME = 30
GRID_COLS = 4
for opt in serveropts:
	if opt[0] == 'name': server = opt[1] # Set the server name
	if opt[0] == 'debug':
		if opt[1] == "1": DEBUG = True # Set the DEBUG flag	
	if opt[0] == 'refresh': REFRESH_TIME = opt[1] # Set the refresh time in seconds
	if opt[0] == 'gridcols': GRID_COLS = int(opt[1]) # Set the number of columns to display the grid

# Get options from [grid] in /etc/pbswebmon.conf
for opt in gridopts:
	if opt[0] == 'translate_dns': translate_dns = opt[1]
	if opt[0] == 'gridmap': gridmap = opt[1]

print "Content-Type: text/html\n\n"	 # HTML is following
try:
	p = PBSQuery(server)
	nodes = p.getnodes()
	jobs = p.getjobs()
	queues = p.getqueues()
except PBSError, e:
	print "<h3>Error connecting to PBS server:</h3><tt>",e,"</tt>"
	print "<p>Please check configuration in ", CONFIG_FILE, "</p>"
	sys.exit(1)


# Import information after ? to have information on checkboxes
form = cgi.FieldStorage()
if DEBUG:
	print "<!-- ",form.getvalue('refresh'),"-->"
	print "<!-- ",sys.argv[0],"-->"

str_checkboxes = [ 'node', 'header', 'job', 'refresh' ]
checkboxes = {}
try:
	for lst in str_checkboxes:
		if form.getvalue(lst) == 'yes':
			checkboxes[lst] = 1
		else:
			checkboxes[lst] = 0
except:
	for lst in str_checkboxes:
		checkboxes[lst] = 0

if DEBUG:
	print "<!-- ",checkboxes,"-->"

# Print the header
header(checkboxes)
print '''
<body>'''

if translate_dns == 'yes':
	userdnmap = get_poolmapping(gridmap)
else:
	userdnmap = {}

if len(nodelist) == 0:
	nodelist=nodes.keys()
	nodelist.sort()

# Print the cluster status table
print_summary(sys.argv[0], form, checkboxes)

# Print the user status table
print "			<td>"
users = fill_user_list(jobs)
print_user_summary(users)
print "			</td>"

# Print the queues status table
print "			<td>"
print_queue_summary(queues)
print "			</td>"

# print the nodes status table
print "			<td>"
print_node_summary(nodes)
print '''			</td>
		</tr>
	</table>
</div> <!-- class='summary_box' -->
'''

#print "<br clear='all' style=\"clear: inherit;\">"
#print "<p></p>"
print "<div class=\"detail_box\">"

# Show all lame and informations
if DEBUG:
	print "<!-- ",nodelist,"-->"
print_lame_list(nodelist, nodes)
print "<p></p>"

# Show all jobs
print_job_list()

print'''</div>'''

print"</body>\n</html>"

