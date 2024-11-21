#!/bin/bash

# Get all the IP addresses
#p_address_list=$(hostname -I)

#echo "IP list: $ip_address_list"

# Get the first IP address
ip_address=$(hostname -I | cut -d' ' -f1)

# Print the IP address
#echo "The first IP address is:"
echo "$ip_address"
