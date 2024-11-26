import cv2
import os
import threading

class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		
		if not os.path.isfile(self.filename):
			raise IOError(f"Error: File {filename} does not exist")
		
		self.cap = cv2.VideoCapture(filename)
		self.frameNum = 0
		self.encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 90]


		self.lock = threading.Lock()

		if not self.cap.isOpened():
			raise IOError(f"Error: Could not open video: {filename}. Format: {self.format}")
		
	def nextFrame(self):
		"""Get next frame."""
		with self.lock:  # Use the lock to ensure only one thread reads at a time
			ret, frame = self.cap.read()
			if ret and frame is not None and frame.size > 0: 
				self.frameNum += 1
				
				try:
					ret, buffer = cv2.imencode('.jpg', frame, self.encode_params)
					if ret: 
						return buffer.tobytes()
					else: 
						print("Error: Could not encode frame.")
						return None
				except Exception as e:
					print(f"Error: Could not encode frame {self.frameNum}. {e}")
					return None
			else:
				print(f"Error reading frame {self.frameNum}.")
				return None


	def reset(self):
		"""Reset frame number."""
		print('-'*60)
		print(f"Video ended. Restarting video. Frame number: {self.frameNum}")
		print('-'*60)
		self.frameNum = 0
		self.cap = cv2.VideoCapture(self.filename)
		
		# Read the first frame after reset
		ret, frame = self.cap.read()
		if ret:
			print("First frame after reset read successfully.")
		else:
			print("Failed to read the first frame after reset.")


		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum
	
	def __del__(self):
		"""Clean up."""
		self.cap.release()
	