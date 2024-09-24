import json
import mimetypes
from flask import current_app

import boto3
from botocore.exceptions import ClientError


class RunRekognition:
    def __init__(self):
        self.region = current_app.config["AWS_DEFAULT_REGION"]
        self.bucketname = current_app.config["BUCKET"]
        self.confidencestr = current_app.config["CONFIDENCE"]
        self.confidence = float(self.confidencestr)
        self.boto3client = boto3.client(
            "rekognition",
            region_name=self.region,
            aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=current_app.config["AWS_SECRET_KEY"],
        )
        self.s3 = boto3.client(
            "s3",
            aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=current_app.config["AWS_SECRET_KEY"],
        )

    def get_labels(self, s3_url):
        # Parse the S3 URL to get bucket name and object key
        from urllib.parse import urlparse
        parsed_url = urlparse(s3_url)
        bucket_name = parsed_url.netloc.split('.')[0]
        object_key = parsed_url.path.lstrip('/')

        response = self.boto3client.detect_labels(
            Image={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': object_key
                }
            }
        )

        image_labels = []
        for label in response["Labels"]:
            if label["Confidence"] > self.confidence:
                image_labels.append(label["Name"].lower())
        
        # Generate a prompt by concatenating the image labels
        return ", ".join(image_labels)

    def get_text(self, file_dir):
        with open(file_dir, "rb") as image:
            response = self.boto3client.detect_text(Image={"Bytes": image.read()})

        image_text = []
        for text in response["TextDetections"]:
            if text["Confidence"] > self.confidence:
                image_text.append(text["DetectedText"].lower())
        # Generate a prompt by concatenating the image labels
        return ", ".join(image_text)

    def get_celeb(self, file_dir):
        with open(file_dir, "rb") as image:
            response = self.boto3client.recognize_celebrities(
                Image={"Bytes": image.read()}
            )
        print(response)
        image_text = []
        for text in response["CelebrityFaces"]:
            if text["MatchConfidence"] > self.confidence:
                image_text.append(text["Name"].lower())
        # Generate a prompt by concatenating the image labels
        return ", ".join(image_text)

    def bucket_exists(self):
        try:
            # 'HeadBucket' only retrieves metadata about the bucket, not its contents
            self.s3.head_bucket(Bucket=self.bucketname)
            return True
        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                return False
            elif error_code == 403:
                print(
                    f"Permissions denied for bucket: {self.bucketname}. Assuming it exists."
                )
                return True
            else:
                # Some other unexpected error occurred
                raise

    def create_s3_bucket(self):
        image_uri = None
        if not self.bucket_exists():
            location = {"LocationConstraint": self.region} if self.region else {}
            image_uri = self.s3.create_bucket(
                Bucket=self.bucketname, CreateBucketConfiguration=location
            )
            # self.make_bucket_public(s3)
        return image_uri

    def make_bucket_public(self):
        public_bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{self.bucketname}/*",
                }
            ],
        }
        self.s3.put_bucket_policy(
            Bucket=self.bucketname, Policy=json.dumps(public_bucket_policy)
        )

    def upload_to_bucket(self, original_filename, file_object):
        print(original_filename)
        self.create_s3_bucket()
        try:
            blob_name = original_filename
        
        # Use put_object instead of upload_file
            file_object.seek(0)
        
        # Read the file content
            file_content = file_object.read()
            
            # Guess the content type
            content_type, _ = mimetypes.guess_type(original_filename)
            if content_type is None:
                content_type = 'application/octet-stream'
            
            # Upload to S3
            self.s3.put_object(
                Bucket=self.bucketname,
                Key=blob_name,
                Body=file_content,
                ContentType=content_type
            )
            
            print(f"Image uploaded successfully to s3://{self.bucketname}/{blob_name}")
            
            # Construct the public URL for the uploaded object
            # Note: This assumes the object is publicly accessible.
            url = f"https://{self.bucketname}.s3.amazonaws.com/{blob_name}"
            return url
        except Exception as e:
            print(f"Error uploading {blob_name} to {self.bucketname}. Error: {e}")
            return None
