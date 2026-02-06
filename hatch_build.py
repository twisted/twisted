# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
from hatchling.metadata.plugin.interface import MetadataHookInterface


class CustomMetadataHook(MetadataHookInterface):
    def update(self, metadata):
        optional_dependencies = self.config["optional-dependencies"]
        for feature, dependencies in list(optional_dependencies.items()):
            if "-" not in feature:
                continue

            # We define all the legacy dependency targets using the
            # underscore for backward compatibility.
            #
            # See: https://github.com/twisted/twisted/pull/11656#issuecomment-1282855123
            legacy_feature = feature.replace("-", "_")
            optional_dependencies[legacy_feature] = dependencies

        metadata["optional-dependencies"] = optional_dependencies
