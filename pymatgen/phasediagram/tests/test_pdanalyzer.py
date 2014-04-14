import unittest
import os

from numbers import Number

from pymatgen.core.composition import Composition
from pymatgen.core.periodic_table import Element
from pymatgen.phasediagram.pdmaker import PhaseDiagram
from pymatgen.phasediagram.pdanalyzer import PDAnalyzer
from pymatgen.phasediagram.entries import PDEntryIO


class PDAnalyzerTest(unittest.TestCase):

    def setUp(self):
        module_dir = os.path.dirname(os.path.abspath(__file__))
        (elements, entries) = PDEntryIO.from_csv(os.path.join(module_dir,
                                                              "pdentries_test.csv"))
        self.pd = PhaseDiagram(entries)
        self.analyzer = PDAnalyzer(self.pd)

    def test_get_e_above_hull(self):
        for entry in self.pd.stable_entries:
            self.assertLess(self.analyzer.get_e_above_hull(entry), 1e-11,
                            "Stable entries should have e above hull of zero!")
        for entry in self.pd.all_entries:
            if entry not in self.pd.stable_entries:
                e_ah = self.analyzer.get_e_above_hull(entry)
                self.assertGreaterEqual(e_ah, 0)
                self.assertTrue(isinstance(e_ah, Number))

    def test_get_equilibrium_reaction_energy(self):
        for entry in self.pd.stable_entries:
            self.assertLessEqual(
                self.analyzer.get_equilibrium_reaction_energy(entry), 0,
                "Stable entries should have negative equilibrium reaction energy!")

    def test_get_decomposition(self):
        for entry in self.pd.stable_entries:
            self.assertEquals(len(self.analyzer.get_decomposition(entry.composition)), 1,
                              "Stable composition should have only 1 decomposition!")
        dim = len(self.pd.elements)
        for entry in self.pd.all_entries:
            ndecomp = len(self.analyzer.get_decomposition(entry.composition))
            self.assertTrue(ndecomp > 0 and ndecomp <= dim,
                            "The number of decomposition phases can at most be equal to the number of components.")

        #Just to test decomp for a ficitious composition
        ansdict = {entry.composition.formula: amt
                   for entry, amt in
                   self.analyzer.get_decomposition(Composition("Li3Fe7O11")).items()}
        expected_ans = {"Fe2 O2": 0.0952380952380949,
                        "Li1 Fe1 O2": 0.5714285714285714,
                        "Fe6 O8": 0.33333333333333393}
        for k, v in expected_ans.items():
            self.assertAlmostEqual(ansdict[k], v)

    def test_get_transition_chempots(self):
        for el in self.pd.elements:
            self.assertLessEqual(len(self.analyzer.get_transition_chempots(el)),
                                 len(self.pd.facets))

    def test_get_element_profile(self):
        for el in self.pd.elements:
            for entry in self.pd.stable_entries:
                if not (entry.composition.is_element):
                    self.assertLessEqual(len(self.analyzer.get_element_profile(el, entry.composition)),
                                         len(self.pd.facets))

    def test_get_get_chempot_range_map(self):
        elements = [el for el in self.pd.elements if el.symbol != "Fe"]
        self.assertEqual(len(self.analyzer.get_chempot_range_map(elements)), 10)

    def test_getmu_vertices_stability_phase(self):
        results = self.analyzer.getmu_vertices_stability_phase(Composition.from_formula("LiFeO2"), Element("O"))
        self.assertAlmostEqual(results[5][Element("O")], -7.11535414)
        self.assertAlmostEqual(results[10][Element("Li")], -3.93161519)
        self.assertAlmostEqual(results[0][Element("Fe")], -10.45183356)

    def test_getmu_range_stability_phase(self):
        results = self.analyzer.getmu_range_stability_phase(Composition.from_formula("LiFeO2"), Element("O"))
        self.assertAlmostEqual(results[Element("O")][1], -4.4501812249999997)
        self.assertAlmostEqual(results[Element("Fe")][0], -6.5961470999999996)
        self.assertAlmostEqual(results[Element("Li")][0], -3.6250022625000007)

if __name__ == '__main__':
    unittest.main()

