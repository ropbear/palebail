from multiprocessing import Pool
from pathlib import Path
import shutil
import tldextract
import boto3
import os
import sys
import datetime
import tzlocal
import argparse
import json
import configparser
from typing import Tuple, Callable

REGIONS = [
    "us-east-2","us-east-1","us-west-1",
    "us-west-2","ap-east-1","ap-south-1",
    "ap-northeast-3","ap-northeast-2",
    "ap-northeast-1","ap-southeast-1",
    "ap-southeast-2","ca-central-1",
    "cn-north-1","cn-northwest-1","eu-central-1",
    "eu-west-1","eu-west-2","eu-west-3",
    "eu-north-1","me-south-1","sa-east-1"
]

class FireProx(object):
    def __init__(self):
        self.profile_name = ''
        self.access_key = ''
        self.secret_access_key = ''
        self.session_token = ''
        self.region = REGIONS[0]
        self.command = ''
        self.api_id = ''
        self.url = ''
        self.api_list = []
        self.client = None
        self.help = ''
        self.proxy = ''

    def __str__(self):
        return 'FireProx()'

    def _try_instance_profile(self) -> bool:
        """Try instance profile credentials

        :return:
        """
        try:
            self.client = boto3.client(
                'apigateway',
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_access_key
            )
            self.client.get_account()
            self.region = self.client._client_config.region_name
            return True
        except:
            return False

    def error(self, error):
        print(self.help)
        sys.exit(error)

    def get_template(self):
        url = self.url
        if url[-1] == '/':
            url = url[:-1]

        title = 'fireprox_palebail'
        version_date = f'{datetime.datetime.now():%Y-%m-%dT%XZ}'
        template = '''
        {
          "swagger": "2.0",
          "info": {
            "version": "{{version_date}}",
            "title": "{{title}}"
          },
          "basePath": "/",
          "schemes": [
            "https"
          ],
          "paths": {
            "/": {
              "x-amazon-apigateway-any-method": {
                "parameters": [
                  {
                    "name": "proxy",
                    "in": "path",
                    "required": true,
                    "type": "string"
                  },
                  {
                    "name": "X-My-X-Forwarded-For",
                    "in": "header",
                    "required": false,
                    "type": "string"
                  }
                ],
                "responses": {},
                "x-amazon-apigateway-integration": {
                  "uri": "{{url}}/",
                  "responses": {
                    "default": {
                      "statusCode": "200"
                    }
                  },
                  "requestParameters": {
                    "integration.request.path.proxy": "method.request.path.proxy",
                    "integration.request.header.X-Forwarded-For": "method.request.header.X-My-X-Forwarded-For"
                  },
                  "passthroughBehavior": "when_no_match",
                  "httpMethod": "ANY",
                  "cacheNamespace": "irx7tm",
                  "cacheKeyParameters": [
                    "method.request.path.proxy"
                  ],
                  "type": "http_proxy"
                }
              }
            },
            "/{proxy+}": {
              "x-amazon-apigateway-any-method": {
                "produces": [
                  "application/json"
                ],
                "parameters": [
                  {
                    "name": "proxy",
                    "in": "path",
                    "required": true,
                    "type": "string"
                  },
                  {
                    "name": "X-My-X-Forwarded-For",
                    "in": "header",
                    "required": false,
                    "type": "string"
                  }
                ],
                "responses": {},
                "x-amazon-apigateway-integration": {
                  "uri": "{{url}}/{proxy}",
                  "responses": {
                    "default": {
                      "statusCode": "200"
                    }
                  },
                  "requestParameters": {
                    "integration.request.path.proxy": "method.request.path.proxy",
                    "integration.request.header.X-Forwarded-For": "method.request.header.X-My-X-Forwarded-For"
                  },
                  "passthroughBehavior": "when_no_match",
                  "httpMethod": "ANY",
                  "cacheNamespace": "irx7tm",
                  "cacheKeyParameters": [
                    "method.request.path.proxy"
                  ],
                  "type": "http_proxy"
                }
              }
            }
          }
        }
        '''
        template = template.replace('{{url}}', url)
        template = template.replace('{{title}}', title)
        template = template.replace('{{version_date}}', version_date)
        return str.encode(template)

    def create_api(self, url):
        if not url:
            self.error('Please provide a valid URL end-point')
        self.url = url
        self._try_instance_profile()

        template = self.get_template()
        response = self.client.import_rest_api(
            parameters={
                'endpointConfigurationTypes': 'REGIONAL'
            },
            body=template
        )
        resource_id, proxy_url = self.create_deployment(response['id'])
        self.api_id = response['id']
        self.store_api(
            response['id'],
            response['name'],
            response['createdDate'],
            response['version'],
            url,
            resource_id,
            proxy_url
        )
        self.proxy = proxy_url

    def update_api(self, url):
        if not any([self.api_id, url]):
            self.error('Please provide a valid API ID and URL end-point')

        if url[-1] == '/':
            url = url[:-1]

        resource_ids = self.get_resource(self.api_id)
        for path in resource_ids.keys():
            form = r'{proxy}' if path == '/{proxy+}' else ''
            response = self.client.update_integration(
                restApiId=self.api_id,
                resourceId=resource_ids[path],
                httpMethod='ANY',
                patchOperations=[
                    {
                        'op': 'replace',
                        'path': '/uri',
                        'value': '{}/{}'.format(url, form),
                    },
                ]
            )
        
    def delete_api(self, api_id):
        if not api_id:
            self.error('Please provide a valid API ID')
        items = self.list_api(api_id)
        for item in items:
            item_api_id = item['id']
            if item_api_id == api_id:
                response = self.client.delete_rest_api(
                    restApiId=api_id
                )
                return True
        return False

    def list_api(self, deleted_api_id=None):
        response = self.client.get_rest_apis()
        for item in response['items']:
            try:
                created_dt = item['createdDate']
                api_id = item['id']
                name = item['name']
                proxy_url = self.get_integration(api_id).replace('{proxy}', '')
                url = f'https://{api_id}.execute-api.{self.region}.amazonaws.com/fireprox/'
            except:
                pass

        return response['items']

    def store_api(self, api_id, name, created_dt, version_dt, url,
                  resource_id, proxy_url):
        pass

    def create_deployment(self, api_id):
        if not api_id:
            self.error('Please provide a valid API ID')

        response = self.client.create_deployment(
            restApiId=api_id,
            stageName='fireprox',
            stageDescription='FireProx Prod',
            description='FireProx Production Deployment'
        )
        resource_id = response['id']
        return (resource_id,
                f'https://{api_id}.execute-api.{self.region}.amazonaws.com/fireprox/')

    def get_resource(self, api_id):
        if not api_id:
            self.error('Please provide a valid API ID')
        response = self.client.get_resources(restApiId=api_id)
        items = response['items']
        ids = {}
        for item in items:
            item_id = item['id']
            item_path = item['path']
            ids[item_path] = item_id
        return ids

    def get_integration(self, api_id):
        if not api_id:
            self.error('Please provide a valid API ID')
        resource_id = self.get_resource(api_id)['/{proxy+}']
        response = self.client.get_integration(
            restApiId=api_id,
            resourceId=resource_id,
            httpMethod='ANY'
        )
        return response['uri']

