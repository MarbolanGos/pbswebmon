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
# get options from config file
import ConfigParser


# Input variables
NODE_STATES=['down','free','job-exclusive','offline','busy','down,offline','down,job-exclusive','state-unknown','down,busy','job-exclusive,busy']
JOB_STATES=['R','Q','E','C','H','W']
REFRESH_TIME = "30"
JOB_EFFIC={}
USER_EFFIC={}
CONFIG_FILE="/etc/pbswebmon.conf"
GRID_COLS=4
DEBUG=False
njobs=-1
users={}

def header():
	""" Print the header of the HTML page.
	The parameter REFRESH_TIME is globaly defined.
	\todo Allow REFRESH_TIME to be included in the parameters file.
	"""
	print '''<html>
<head>
	<title>PBSWebMon</title> 
	<script src="/pbswebmon/table.js" type="text/javascript"></script>
	<script src="/pbswebmon/datasel.js" type="text/javascript"></script>
	<script type="text/javascript">
		var iTimeout;
		/*=window.setTimeout('if (location.reload) location.reload();', %s*1000);*/
		function set_refresh(refresh) {
			if (refresh) {
				if (window.setTimeout) {
					iTimeout = window.setTimeout('if (location.reload) location.reload();', %s*1000);
				}
			} else {
				if (window.clearTimeout) window.clearTimeout(iTimeout);
			}
		}
	</script>
	
	<link rel="stylesheet" type="text/css" href="/pbswebmon/table.css" media="all">
	<link rel="stylesheet" type="text/css" href="/pbswebmon/local.css" media="all">
</head>''' % (REFRESH_TIME, REFRESH_TIME)

def print_summary():
	""" Print the Summary cluster status
	"""
	print "<!-- print_summary -->"
	print "<div class='summary_box'>"
	print '''	<table class='summary_box_table'>
		<tr class='summary_box_entry'>
			<td>
				<b>Cluster status</b><br/>
				%s<br />
				Refreshes every %s seconds. <br />
				<form class="showdetails">
					<INPUT TYPE=CHECKBOX NAME="showdetails" CHECKED  onClick=\"show_hide_data(\'jobdata\', this.checked)\">Show all job details<br />
					<INPUT TYPE=CHECKBOX NAME="Fixed header" CHECKED onClick=\"on_top(\'summary_box\', this.checked)\">Header always on top<br />
					<INPUT TYPE=CHECKBOX NAME="refresh" onClick=\"set_refresh(this.checked)\">Auto-refresh
				</form>
			</td>''' % (strftime("%Y-%m-%d %H:%M:%S"),REFRESH_TIME)

def user_effic(user):
	""" Efficiency for the running user
	\param user The user to be parsed
	\return effic The calculated efficiency
	"""
	effic = 0.0
	if user in USER_EFFIC:
		for job in USER_EFFIC[user]:
			effic += job
		effic /= float(len(USER_EFFIC[user]))*100.0

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
	# user info
	if ownershort in userdnmap:
		ownerdn=userdnmap[ownershort]
	else:
		ownerdn=ownershort

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
	\param kbmem The amount of memory in kB
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
	for user, atts in users.items():
		njobs = '0'
		if 'jobs' in atts.keys():
			njobs = atts['jobs']
			total += njobs
			
			print '''					<tr>
						<td onMouseOver='highlight(\"%s\")' onMouseOut='dehighlight(\"%s\")'title='%s'>%s</td>''' % (user,user,get_dn(user),user)
			for state in JOB_STATES:
				print "						<td>%d</td>" % atts[state]
				totals[state] += atts[state]
			print "						<td>%.0f</td>" % user_effic(user)
			print "					</tr>"



	print '''					<tfoot><tr>
						<td><b>Total</b></td>'''
	for state in JOB_STATES:
		print "						<td>%s</td>" % totals[state]
	print "					</tr></tfoot>"
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
	for s in NODE_STATES:
		tdclass = s
		if (s == "down,job-exclusive"):
			tdclass="down"
		print '''					<tr>
						<td class='%s'>%s</td>
						<td class='%s'>%d</td>
					</tr>''' %(tdclass,s,tdclass,totals[s])
		total += totals[s]
	print '''					<tfoot><tr>
						<td><b>Total</b></td>
						<td>%d</td>
					</tr></tfoot>''' %total
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
	
	for queue, atts in queues.items():
		print "					<tr>"
		print "						<td>",queue, "</td>"

		state = atts['state_count'][0]
		state_counts = state.split()
		statedict = {}
		for entry in state_counts:
			type,count=entry.split(":")
			statedict[type] = count


		for s in headers:
			print "						<td align='right'>",statedict[s],"</td>"
			totals[s] += int(statedict[s])
			
		print "					</tr>"
	print '''					<tfoot><tr>
						<td><b>Total</b></td>'''
	for h in headers:
		print "						<td align='right'>%d</td> " %(totals[h])
	print "					</tr></tfoot>"
	print "				</table>"

def print_key_table():

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
	"""
	print '''	<table style='margin-top:20px'  class=\" table-autosort:0 node_grid\">
		<tr>'''
	count = 0
	def nsort(l):
		""" Sort lames by number
		\param l The list of the lames
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
		if name in nodes:
			node = nodes[name]
			attdict={}
			if 'status' in node.keys():
				attdict = node['status']
			
		if 'state' in node.keys():
			node_state = node['state'][0]
	
			if True: #'jobs' in node.keys():
				if 'jobs' in node.keys():
					myjobs = node['jobs']
					if DEBUG:
						print "<!-- DEBUG myjobs:",myjobs,"-->"
				else:
					myjobs = []
				nusers = '0'
				physmem = 0.0
	
				if 'nusers' in attdict:
					nusers = attdict['nusers'][0]
					if DEBUG:
						print "<!-- DEBUG nusers:",nusers,"-->"
	
				if 'physmem' in attdict:
					physmem = convert_to_gb(attdict['physmem'][0])	
					if DEBUG:
						print "<!-- DEBUG physmem:",physmem,"-->"		
	
				loadave = "n/a"
				if 'loadave' in attdict:
					loadave = attdict['loadave'][0]
					if DEBUG:
						print "<!-- DEBUG loadave:",loadave,"-->"	
				
				# if (njobs == -1) or len(myjobs)== njobs:
				if True:
			# define cell bg color based on state
					if (node_state == 'free' and (len(myjobs) > 0)):
						node_state = 'partfull'
					if (node_state == 'down,job-exclusive'):
						node_state = 'down'
					print "			<td valign='top'>"
					print '''				<form class='%s'>
					<b>%s<INPUT class='job_indiv' TYPE=CHECKBOX NAME="showdetails" CHECKED onClick=\"show_hide_data_id(\'%s\', this.checked)\"><font size=\'2\'>Show jobs</font></b><br />''' % (node_state,name, name)
					print '''					%d jobs, %s users, %.2f GB, %s load
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
						cput = 0.0
						walltime = 1.0
						effic = 0.0
						if DEBUG:
							print "<!-- DEBUG myjob.keys:",myjob.keys(),"-->"
							print "<!-- DEBUG myjob['Resource_List']:",myjob['Resource_List'],"-->"
							print "<!-- DEBUG myjob['resources_used']['mem']:",type(myjob['resources_used']['mem'][0]),"-->"
							print "<!-- DEBUG myjob['Walltime']['Remaining'][0]:",myjob['Walltime']['Remaining'][0],"-->"
						if 'mem' in myjob['resources_used'].keys():
							mem = convert_to_gb(myjob['resources_used']['mem'][0])
							if DEBUG:
								print "<!-- DEBUG mem:",mem,"-->"	
						if  'mem' in myjob['Resource_List'].keys():
							memreq = convert_to_gb(myjob['Resource_List']['mem'][0])
	
						if 'walltime' in myjob['Resource_List'].keys():
							walltime = convert_time(myjob['Resource_List']['walltime'][0])
							if DEBUG:
								print "<!-- DEBUG walltime:",walltime,"-->"	
	
						if 'Remaining' in myjob['Walltime'].keys():
							# cput = walltime - remaining
							cput = int(walltime) - int(myjob['Walltime']['Remaining'][0])
							if DEBUG:
								print "<!-- DEBUG cput:",cput,"-->"	
							
						if 'queue' in myjob:
							myqueue = myjob['queue'][0]
	
						if walltime != 0.0:
							effic = float(cput)/float(walltime)
							if DEBUG:
								print "<!-- DEBUG effic:",effic,"-->"	
	
						wrap=" "
						print "					<span title='"+jidshort+": "+myqueue+"'>"+cpu+ ": "+jidshort+ "</span>"
	
						# user info
						ownerdn = get_dn(ownershort)
							
						print "					<span class= '%s' title='%s'> %-9s</span>" %(ownershort,ownerdn,ownershort)
						print "					<span title='%s/%s s'>" % (cput, walltime)
						if effic < .8:
							print "						<font color='gray'>",
						else:
							if effic > 1.0:
								print "						<font color='red'>",
							else:
								print "						<font color='black'>",
								
						print "%7.2f%%</font> " % (effic*100.0)
						print "					</span>"
						
						# Try and except to test if the user has defined mem in script
						try:
							if mem > memreq and memreq > 0.0:
								print "					<font color='red'>",
							else:
								if mem < 0.5*memreq:
									print "					<font color='gray'>",
								else:
									print "					<font color='black'>",
	
						except:
							memreq = 0.0
							print "					<font color='black'>",
						
	
						print "%.2f/%.2f GB</font>" %(mem,memreq),
						print "<br />\n"
					print "				</span> <!-- class='jobdata' -->"
					print "			</td>"
				if (count and ((count%GRID_COLS)) == GRID_COLS-1):
					if DEBUG:
						print "<!-- ",count,"!-->\n"
					print "		</tr>\n\t\t<tr>\n"
				count += 1
	
	print "	</table> <!-- class=\" table-autosort:0 node_grid\" -->"


def print_job_list():
	print
	print "<!-- Job List -->"
	print "	<table class='example table-sorted-asc table-autosort:0 joblist'>"
	print "		<caption>Jobs</caption>"
	print "		<thead><tr>"
	print "			<th class='table-sortable:default'>Job ID</th>"
	print "			<th class='table-sortable:default'>Username</th>"
	print "			<th class='table-sortable:default'>Queue</th>"
	print "			<th class='table-sortable:default'>Jobname</th>"
	print "			<th class='table-sortable:numeric'>Nodes</th>"
	print "			<th class='table-sortable:default'>State</th>"
	print "			<th class='table-sortable:numeric'>Elapsed Time</th>"
	print "		</tr></thead>"
	
	print "		<tbody>"
	for name,job in jobs.items():
		owner = job['Job_Owner'][0]
		if DEBUG:
			print "<!-- DEBUG: ",owner.split('@')[0],"-->"
		print "			<tr>"
		print "				<td>",name.split('.')[0],"</td>"
		print "				<td>",owner.split('@')[0],"</td>"
		print "				<td>",job['queue'][0],"</td>"
		print "				<td>",job['Job_Name'][0],"</td>"
		if job['Resource_List'].has_key('nodect'):
			print "				<td>",job['Resource_List']['nodect'][0],"</td>"
		else:
			print "				<td></td>"
		print "				<td>",job['job_state'][0],"</td>"
		try:
			walltime = job['resources_used']['walltime'][0]
			print "				<td>",walltime,"</td>"
		except:
			print "				<td></td>"
	
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

for opt in serveropts:
	if opt[0] == 'name':
		server=opt[1] 

for opt in gridopts:
	if opt[0] == 'translate_dns':
		translate_dns = opt[1]
	if opt[0] == 'gridmap':
		gridmap = opt[1]

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

# Print the header
header()
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
print_summary()

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
#print "<div>"

# Show all lame and informations
if DEBUG:
	print "<!-- ",nodelist,"-->"
print_lame_list(nodelist, nodes)

# Show all jobs
print_job_list()

#print"</div>"

print"</body>\n</html>"

