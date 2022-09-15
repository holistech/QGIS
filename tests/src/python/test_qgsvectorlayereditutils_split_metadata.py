# -*- coding: utf-8 -*-
"""QGIS Unit tests for split metadata generation in the QgsVectorLayerEditUtils::splitFeatures

From build dir, run: ctest -R PyQgsVectorLayerEditUtilsSplit -V

.. note:: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
"""
__author__ = 'Soeren Gebbert'
__date__ = '09/14/2022'
__copyright__ = 'Copyright 2022, The QGIS Project'

import qgis  # NOQA
import os
from qgis.core import QgsVectorLayer, QgsDefaultValue
from qgis.core import QgsPointXY as QgsPointXY # To be renamed to: QgsPoint as QgsPointXY
from qgis.testing import start_app, unittest
from qgis.utils import spatialite_connect

# Convenience instances in case you may need them
start_app()


class TestQgsVectorLayerEditUtilsSplitMetadata(unittest.TestCase):
    """Test the correct metadata creation for split operations in the vector edit utils class
    """

    @staticmethod
    def build_table_with_testdata(path: str = "test.sqlite"):
        if os.path.exists(path):
            os.remove(path)
        con = spatialite_connect(path, isolation_level=None)
        cur = con.cursor()
        cur.execute("BEGIN")
        sql = "SELECT InitSpatialMetadata()"
        cur.execute(sql)

        # Create a table with a single polygon geometry that has 3 fields that should store split metadata
        sql = f"CREATE TABLE test_pg (id SERIAL PRIMARY KEY, name STRING NOT NULL, predecessors STRING, " \
              f"operation_type INTEGER, operation_date TEXT)"
        cur.execute(sql)
        sql = f"SELECT AddGeometryColumn('test_pg', 'geometry', 4326, 'POLYGON', 'XY')"
        cur.execute(sql)
        sql = f"INSERT INTO test_pg (id, name, geometry) "
        sql += "VALUES (1, 'polygon', GeomFromText('POLYGON((0 0,3 0,3 3,0 3,0 0))', 4326))"
        cur.execute(sql)
        cur.execute("COMMIT")
        con.close()

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        """Run after all tests"""
        if os.path.exists("test.sqlite"):
            os.remove("test.sqlite")

    def setUp(self):
        """Run before each test."""
        self.build_table_with_testdata()

    def tearDown(self):
        """Run after each test."""
        pass

    def create_layer(self) -> QgsVectorLayer:
        layer = QgsVectorLayer("dbname=test.sqlite table=test_pg (geometry)", "test_pg", "spatialite")
        assert layer.isValid()
        assert layer.isSpatial()
        assert layer.featureCount() == 1, "wrong number of features"
        return layer

    @staticmethod
    def apply_default_values(layer: QgsVectorLayer):
        """Create default values for the three fields"""
        default_predecessors = QgsDefaultValue()
        default_predecessors.setApplyOnUpdate(True)
        default_predecessors.setExpression('CASE WHEN @sm_operation_type IS 1 '
                                           'THEN @sm_predecessor_ids ELSE predecessors END')
        layer.setDefaultValueDefinition(2, default_predecessors)
        default_operation_type = QgsDefaultValue()
        default_operation_type.setApplyOnUpdate(True)
        default_operation_type.setExpression('CASE WHEN @sm_operation_type IS 1 '
                                             'THEN @sm_operation_type ELSE operation_type END')
        layer.setDefaultValueDefinition(3, default_operation_type)
        default_operation_date = QgsDefaultValue()
        default_operation_date.setApplyOnUpdate(True)
        default_operation_date.setExpression('CASE WHEN @sm_operation_type IS 1 '
                                             'THEN @sm_operation_date ELSE operation_type END')
        layer.setDefaultValueDefinition(4, default_operation_date)

    def test_split_polygon_with_split_expression(self):
        """Test the splitFeature method with default value definitions"""

        layer = self.create_layer()
        self.apply_default_values(layer)
        layer.startEditing()
        assert layer.splitFeatures([QgsPointXY(-1, -1), QgsPointXY(4, 4)], 0) == 0, "Error creating a simple split"
        assert layer.commitChanges(), "this commit should work"
        assert layer.featureCount() == 2, "wrong number of features"

        for feature in layer.getFeatures():
            if feature.id() == 2:
                assert feature["predecessors"] == 1
                assert feature["operation_type"] == 1
                assert feature["operation_date"]

    def test_split_polygon_with_split_expression_id_autogen_problem(self):
        """Test the splitFeature method with default value definitions that produce negative predecessor ids
        if the layer was not saved between the splitting operations"""

        layer = self.create_layer()
        self.apply_default_values(layer)
        layer.startEditing()
        assert layer.splitFeatures([QgsPointXY(-1, -1), QgsPointXY(4, 4)], 0) == 0, "Error creating a simple split"
        assert layer.splitFeatures([QgsPointXY(-1, 4), QgsPointXY(4, -1)], 0) == 0, "Error creating a simple split"
        assert layer.splitFeatures([QgsPointXY(-1, 2), QgsPointXY(4, 2)], 0) == 0, "Error creating a simple split"
        assert layer.commitChanges(), "this commit should work"
        assert layer.featureCount() == 7, "wrong number of features"

        for feature in layer.getFeatures():
            if feature.id() == 2:
                assert feature["predecessors"] == 1
                assert feature["operation_type"] == 1
                assert feature["operation_date"]
            if feature.id() == 4:
                assert feature["predecessors"] < 0
                assert feature["operation_type"] == 1
                assert feature["operation_date"]
            if feature.id() == 5:
                assert feature["predecessors"] < 0
                assert feature["operation_type"] == 1
                assert feature["operation_date"]
            if feature.id() == 6:
                assert feature["predecessors"] < 0
                assert feature["operation_type"] == 1
                assert feature["operation_date"]
            if feature.id() == 7:
                assert feature["predecessors"] < 0
                assert feature["operation_type"] == 1
                assert feature["operation_date"]

    def test_multisplit_polygon_with_split_expression(self):
        """Test the splitFeature method with default value definitions and multiple split statements"""

        layer = self.create_layer()
        self.apply_default_values(layer)
        layer.startEditing()
        assert layer.splitFeatures([QgsPointXY(-1, -1), QgsPointXY(4, 4)], 0) == 0, "Error creating a simple split"
        assert layer.commitChanges(), "this commit should work"
        assert layer.featureCount() == 2, "wrong number of features"

        layer.startEditing()
        assert layer.splitFeatures([QgsPointXY(-1, 4), QgsPointXY(4, -1)], 0) == 0, "Error creating a simple split"
        assert layer.commitChanges(), "this commit should work"
        assert layer.featureCount() == 4, "wrong number of features"

        layer.startEditing()
        assert layer.splitFeatures([QgsPointXY(-1, 2), QgsPointXY(4, 2)], 0) == 0, "Error creating a simple split"
        assert layer.commitChanges(), "this commit should work"
        assert layer.featureCount() == 7, "wrong number of features"

        for feature in layer.getFeatures():
            if feature.id() == 1:
                assert feature["predecessors"] is not None
                assert feature["operation_type"] is not None
                assert feature["operation_date"] is not None
            if feature.id() == 2:
                assert feature["predecessors"] == 1
                assert feature["operation_type"] == 1
                assert feature["operation_date"]
            if feature.id() == 3:
                assert feature["predecessors"] == 1
                assert feature["operation_type"] == 1
                assert feature["operation_date"]
            if feature.id() == 4:
                assert feature["predecessors"] == 2
                assert feature["operation_type"] == 1
                assert feature["operation_date"]
            if feature.id() == 5:
                assert feature["predecessors"] == 2
                assert feature["operation_type"] == 1
                assert feature["operation_date"]
            if feature.id() == 6:
                assert feature["predecessors"] == 3
                assert feature["operation_type"] == 1
                assert feature["operation_date"]
            if feature.id() == 7:
                assert feature["predecessors"] == 4
                assert feature["operation_type"] == 1
                assert feature["operation_date"]

    def test_split_polygon_without_split_expression(self):
        """Test the splitFeature method without default value definitions"""

        layer = self.create_layer()
        layer.startEditing()
        assert layer.splitFeatures([QgsPointXY(-1, -1), QgsPointXY(4, 4)], 0) == 0, "Error creating a simple split"
        assert layer.commitChanges(), "this commit should work"
        assert layer.featureCount() == 2, "wrong number of features"

        for feature in layer.getFeatures():
            if feature.id() == 2:
                assert feature["predecessors"] is not None
                assert feature["operation_type"] is not None
                assert feature["operation_date"] is not None


if __name__ == '__main__':
    unittest.main()
