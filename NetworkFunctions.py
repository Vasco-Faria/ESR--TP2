import subprocess

def getSelfIP():
		try:
			# Run the Bash script
			result = subprocess.run(
				["bash", "get_ip.sh"], 
				capture_output=True, 
				text=True, 
				check=True
			)
			# Print the output of the script
			print(f"Script output of self IP:\n{result.stdout}")
			return result.stdout.strip()
		except subprocess.CalledProcessError as e:
			# Handle errors in running the script
			print(f"Error occurred: {e.stderr}")