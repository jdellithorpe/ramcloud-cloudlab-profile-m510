"""
Allocate a cluster of CloudLab machines for RAMCloud, specifically on CloudLab 
Utah m510 machines.

Instructions:
All machines will share an nfs filesystem mounted at /shome. This filesystem
is exported by a special node called `rcnfs'.

All experiment management must be performed on the node called `rcmaster'.

To run RAMCloud, first clone the repository from github into /shome.
Next, run /local/scripts/localconfigGen.py with the number of nodes - 2 as
a command line argument. Save the output of this command to a file called
localconfig.py under RAMCloud/scripts.

The above steps should be sufficient to run ClusterPerf on the allocated
cluster.
"""

import re

import geni.aggregate.cloudlab as cloudlab
import geni.portal as portal
import geni.rspec.pg as pg
import geni.urn as urn

# Allows for general parameters like disk image to be passed in. Useful for
# setting up the cloudlab dashboard for this profile.
pc = portal.Context()

# The possible set of base disk-images that this cluster can be booted with.
# The second field of every tupule is what is displayed on the cloudlab
# dashboard.
images = [ ("UBUNTU16-64-STD", "Ubuntu 16.04 (64-bit)") ]

# The possible set of node-types this cluster can be configured with. Currently 
# only m510 machines are supported.
hardware_types = [ ("m510", "m510 (CloudLab Utah, Intel Xeon-D)") ]

# Default the disk image to 64-bit Ubuntu 15.04
pc.defineParameter("image", "Disk Image",
        portal.ParameterType.IMAGE, images[0], images,
        "Specify the base disk image that all the nodes of the cluster " +\
        "should be booted with.")

pc.defineParameter("hardware_type", "Hardware Type",
                   portal.ParameterType.NODETYPE,
                   hardware_types[0], hardware_types)

# Default the cluster size to 4 nodes (minimum requires to support a 
# replication factor of 3). 
pc.defineParameter("num_rcnodes", "Cluster Size",
        portal.ParameterType.INTEGER, 4, [],
        "Specify the number of RAMCloud servers. For a replication factor " +\
        "of 3 the minimum number of RAMCloud servers is 4 (1 in-memory " +\
        "copy + 3 on-disk replicas). Note that the total " +\
        "number of servers in the experiment will be this number + 2 (one " +\
        "additional server for rcmaster, and one for rcnfs). To check " +\
        "availability of nodes, visit " +\
        "\"https://www.cloudlab.us/cluster-graphs.php\"")

params = pc.bindParameters()

# Create a Request object to start building the RSpec.
request = pc.makeRequestRSpec()

# Create a local area network.
rclan = request.LAN()
rclan.best_effort = True
rclan.vlan_tagging = True
rclan.link_multiplexing = True

# Setup node names so that existing RAMCloud scripts can be used on the
# cluster.
hostnames = ["rcmaster", "rcnfs"]
for i in range(params.num_rcnodes):
    hostnames.append("rc%02d" % (i + 1))

rcnfs_nfs_export_dir = "/local/nfs"
rcXX_backup_dir = "/local/rcbackup"

# Setup the cluster one node at a time.
for host in hostnames:
    node = request.RawPC(host)
    node.hardware_type = params.hardware_type
    node.disk_image = urn.Image(cloudlab.Utah, "emulab-ops:%s" % params.image)

    node.addService(pg.Execute(shell="sh", 
        command="sudo /local/repository/setup.sh %s %s" % \
        (rcnfs_nfs_export_dir, rcXX_backup_dir)))

    if host == "rcnfs":
        # Ask for a 200GB file system to export via NFS
        nfs_bs = node.Blockstore(host + "nfs_bs", rcnfs_nfs_export_dir)
        nfs_bs.size = "200GB"

    pattern = re.compile("^rc[0-9][0-9]$")
    if pattern.match(host):
        # Ask for a 200GB file system for backups
        backup_bs = node.Blockstore(host + "backup_bs", rcXX_backup_dir)
        backup_bs.size = "200GB"

    # Add this node to the LAN.
    iface = node.addInterface("if1")
    rclan.addInterface(iface)

# Generate the RSpec
pc.printRequestRSpec(request)
