#very simple module for easily managing simple key/value json files

import os
import json

class RegistryFile:
    def __init__(self, file='registry'):
        self.file = file

    def __getRegistryPath(self):
        #builds the registry file path
        path = os.path.join(os.getcwd(), '.data')
        if not os.path.isdir(path):
            os.makedirs(path)
        
        path = os.path.join(path, f'{self.file}.json')
        return path
    
    def getFilePath(self):
        return self.__getRegistryPath()

    def __getRegistryJSONDictionary(self):
        #returns the Registry json file as a dictionary
        path = self.__getRegistryPath()

        if os.path.exists(path):
            with open(path, 'r+') as f:
                registry = json.load(f)
        else:
            registry = {}

        return registry

    def __saveRegistryFile(self, registry):
        #updates the Registry file
        path = self.__getRegistryPath()

        with open(path, 'w') as f:
            json.dump(registry, f, indent = 4)

    def __is_serializable(value):
        try:
            json.dumps(value)
            return True
        except(TypeError, OverflowError):
            return False
        
    def setValue(self, key, value):
        #saves a value to the registry file
        registry = self.__getRegistryJSONDictionary()

        if not RegistryFile.__is_serializable(value):
            value = str(value)

        registry[key] = value
        self.__saveRegistryFile(registry)

    def getValue(self, key, default=None):
        #returns a value from the registry file
        registry = self.__getRegistryJSONDictionary()

        if key in registry.keys():
            return registry[key]
        else:
            return default