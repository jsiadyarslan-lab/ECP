# M3-CA0 v1 — Authored Candidate Case-Set (source document)

Format: M3-CA0V1-case-set-md-2. Authored under owner order M3-CA0 v1
(order reference sha256 2695594b70b238959b5c7ffa9180c8adb16b6a66588fdfa0eb53685d900459fd). Authoring provenance and pool design
are recorded in the tail blocks and the provenance sidecar.

CASE ID: N-001
PROPOSED_REASONING_FAMILY: transitive-relational
STRUCTURAL_SIGNATURE: single 4-entity strict-order chain, 3 facts + transitivity + asymmetry, 3-step forward query
PREMISES:
1. The vex is taller than the lum.
2. The lum is taller than the tor.
3. The tor is taller than the qid.
4. For any two objects, if the first is taller than the second, then the second is not taller than the first.
5. For any three objects, if the first is taller than the second and the second is taller than the third, then the first is taller than the third.
QUESTION: Is the vex taller than the qid? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A single determinate verdict (yes / no / cannot be determined) that follows from the stated relations alone, together with the premises actually used.
INTENDED_CORRECT_ANSWER: Yes — the vex is taller than the qid.
DERIVATION:
1. From premise 1 and premise 2, by transitivity (premise 5): the vex is taller than the tor.
2. From that result and premise 3, again by transitivity: the vex is taller than the qid.
3. The queried relation is derivable in two closure steps; the answer is yes. (Asymmetry, premise 4, is not needed for this derivation but is consistent with it.)
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the vex is taller than the qid
FORBIDDEN_SHORTCUTS:
- Do not infer the answer from the order in which the objects are mentioned in the premises.
- Do not use real-world knowledge about objects with similar-sounding names; only the stated relations may be used.
FORMAL:
```json
{
  "entities": [
    "vex",
    "lum",
    "tor",
    "qid"
  ],
  "premises": [
    {
      "args": [
        "vex",
        "lum"
      ],
      "kind": "rel_fact",
      "relation": "taller"
    },
    {
      "args": [
        "lum",
        "tor"
      ],
      "kind": "rel_fact",
      "relation": "taller"
    },
    {
      "args": [
        "tor",
        "qid"
      ],
      "kind": "rel_fact",
      "relation": "taller"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "taller"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "y",
          "x"
        ],
        "negated": true,
        "relation": "taller"
      },
      "vars": [
        "x",
        "y"
      ]
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "taller"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "taller"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "taller"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    }
  ],
  "query": {
    "args": [
      "vex",
      "qid"
    ],
    "relation": "taller"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: The transitivity-of-taller puzzle shape is common in public corpora; the entity vocabulary is invented and the premise set is minimal, so verbatim retrieval of this exact case is unlikely, though the pattern family is widely present.
AMBIGUITY_RISK: Low. 'Taller than' is a familiar strict order, both governing rules are stated explicitly, and no quantifier scope issues arise.
STRUCTURAL_UNIQUENESS_RATIONALE: A single four-entity chain with both asymmetry and transitivity supplied and no distractors; the query spans the full chain and the derivation depth is exactly two closure steps.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: The case is presented as natural-language premises and a question; the formal layer is protected qualification material not shown to any evaluated system.
KNOWN_LIMITATION: A system that cannot parse comparative relations in natural language may fail to access the transitivity capability through this representation; such a failure does not by itself establish absence of the capability.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: The transitivity-of-taller puzzle shape is common in public corpora; the entity vocabulary is invented and the premise set is minimal, so verbatim retrieval of this exact case is unlikely, though the pattern family is widely present.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-002
PROPOSED_REASONING_FAMILY: transitive-relational
STRUCTURAL_SIGNATURE: two disconnected strict-order chains (2+3 entities), 5 entities, cross-chain query with no link
PREMISES:
1. The pim is older than the quar.
2. The ros is older than the sul.
3. The tav is older than the ros.
4. For any three objects, if the first is older than the second and the second is older than the third, then the first is older than the third.
5. For any two objects, if the first is older than the second, then the second is not older than the first.
QUESTION: Is the pim older than the sul? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Recognition that the queried pair spans two unlinked chains, producing a genuine 'cannot be determined' rather than a forced verdict.
INTENDED_CORRECT_ANSWER: Cannot be determined — the premises connect the pim only to the quar, and the tav/ros/sul chain separately; no premise links the two chains.
DERIVATION:
1. The premises contain two disconnected chains: pim > quar, and tav > ros > sul.
2. Transitivity (premise 4) can only combine relations inside one chain; no premise relates any member of {pim, quar} to any member of {tav, ros, sul}.
3. Neither 'the pim is older than the sul' nor its negation is derivable from the premises.
4. The answer is cannot be determined.
GROUND_TRUTH_CLASS: INDETERMINATE
GROUND_TRUTH_STATEMENT: the pim is older than the sul
FORBIDDEN_SHORTCUTS:
- Do not assume a common ordering (such as naming or listing order) links the two chains.
- Do not treat the absence of a linking premise as evidence for a negative answer.
FORMAL:
```json
{
  "entities": [
    "pim",
    "quar",
    "ros",
    "sul",
    "tav"
  ],
  "premises": [
    {
      "args": [
        "pim",
        "quar"
      ],
      "kind": "rel_fact",
      "relation": "older"
    },
    {
      "args": [
        "ros",
        "sul"
      ],
      "kind": "rel_fact",
      "relation": "older"
    },
    {
      "args": [
        "tav",
        "ros"
      ],
      "kind": "rel_fact",
      "relation": "older"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "older"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "older"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "older"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "older"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "y",
          "x"
        ],
        "negated": true,
        "relation": "older"
      },
      "vars": [
        "x",
        "y"
      ]
    }
  ],
  "query": {
    "args": [
      "pim",
      "sul"
    ],
    "relation": "older"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: SHALLOW
RETRIEVAL_RISK: The disconnected-chain calibrated-abstention design is a known evaluation shape; the invented entity vocabulary and the specific 2+3 split reduce verbatim retrieval likelihood.
AMBIGUITY_RISK: Low. The question explicitly offers 'cannot be determined' as an answer, and the two chains are cleanly separated.
STRUCTURAL_UNIQUENESS_RATIONALE: A five-entity domain split into an unlinked pair and a three-chain, with the query crossing the gap; distinct from single-chain cases by the deliberate absence of any cross-link and from other abstention cases by the purely relational (non-propositional) mechanism.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: A system nudged toward always producing a definite verdict may misreport indeterminacy as a guess; the representation carries no hint that abstention is the designed answer.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: The disconnected-chain calibrated-abstention design is a known evaluation shape; the invented entity vocabulary and the specific 2+3 split reduce verbatim retrieval likelihood.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-003
PROPOSED_REASONING_FAMILY: transitive-relational
STRUCTURAL_SIGNATURE: 4-event temporal chain, reversed-direction query refuted via transitivity + asymmetry
PREMISES:
1. The event aur happens before the event bel.
2. The event bel happens before the event cic.
3. The event cic happens before the event dur.
4. For any two events, if the first happens before the second, then the second does not happen before the first.
5. For any three events, if the first happens before the second and the second happens before the third, then the first happens before the third.
QUESTION: Does the event cic happen before the event aur? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A refutation of the reversed-direction query: the forward order is derived first, and asymmetry then converts it into a definite negative.
INTENDED_CORRECT_ANSWER: No — the event cic does not happen before the event aur.
DERIVATION:
1. From premises 1 and 2, by transitivity (premise 5): the event aur happens before the event cic.
2. Applying asymmetry (premise 4) to 'aur happens before cic': the event cic does not happen before the event aur.
3. The queried statement is refuted; the answer is no.
GROUND_TRUTH_CLASS: CONTRADICTED
GROUND_TRUTH_STATEMENT: the event cic happens before the event aur
FORBIDDEN_SHORTCUTS:
- Do not answer from the order of mention (aur, bel, cic, dur) rather than from the stated relations.
- Do not report 'cannot be determined': the premises refute the queried direction.
FORMAL:
```json
{
  "entities": [
    "aur",
    "bel",
    "cic",
    "dur"
  ],
  "premises": [
    {
      "args": [
        "aur",
        "bel"
      ],
      "kind": "rel_fact",
      "relation": "before"
    },
    {
      "args": [
        "bel",
        "cic"
      ],
      "kind": "rel_fact",
      "relation": "before"
    },
    {
      "args": [
        "cic",
        "dur"
      ],
      "kind": "rel_fact",
      "relation": "before"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "before"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "y",
          "x"
        ],
        "negated": true,
        "relation": "before"
      },
      "vars": [
        "x",
        "y"
      ]
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "before"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "before"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "before"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    }
  ],
  "query": {
    "args": [
      "cic",
      "aur"
    ],
    "relation": "before"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Temporal before-chains with reversed queries appear in public corpora; the invented event labels and the explicit asymmetry premise make this instance unlikely to be retrieved verbatim.
AMBIGUITY_RISK: Low. 'Happens before' is unambiguous, and both rules are stated.
STRUCTURAL_UNIQUENESS_RATIONALE: A reversed-direction query over a four-event temporal chain: the system must derive the forward order and then apply asymmetry to answer 'no' rather than 'cannot be determined', distinguishing it from forward-query and disconnect designs.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Temporal comparative parsing is representation-sensitive; failure to parse 'happens before' correctly would mask the underlying order-reasoning capability.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Temporal before-chains with reversed queries appear in public corpora; the invented event labels and the explicit asymmetry premise make this instance unlikely to be retrieved verbatim.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-004
PROPOSED_REASONING_FAMILY: transitive-relational
STRUCTURAL_SIGNATURE: 5-container nesting chain + tail-attached distractor containment, 6 entities, 4-step query
PREMISES:
1. The dot is inside the alpha.
2. The alpha is inside the beta.
3. The beta is inside the gamma.
4. The gamma is inside the delta.
5. The eps is inside the gamma.
6. For any three objects, if the first is inside the second and the second is inside the third, then the first is inside the third.
QUESTION: Is the dot inside the delta? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A four-step containment derivation that ignores the distractor premise about the eps.
INTENDED_CORRECT_ANSWER: Yes — the dot is inside the delta.
DERIVATION:
1. From premises 1 and 2, by transitivity (premise 6): the dot is inside the beta.
2. From that result and premise 3: the dot is inside the gamma.
3. From that result and premise 4: the dot is inside the delta.
4. The answer is yes. (Premise 5, about the eps, is irrelevant to the query.)
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the dot is inside the delta
FORBIDDEN_SHORTCUTS:
- Do not use the distractor premise about the eps as if it concerned the dot.
- Do not answer from the number of premises; the containment chain must be followed step by step.
FORMAL:
```json
{
  "entities": [
    "dot",
    "alpha",
    "beta",
    "gamma",
    "delta",
    "eps"
  ],
  "premises": [
    {
      "args": [
        "dot",
        "alpha"
      ],
      "kind": "rel_fact",
      "relation": "inside"
    },
    {
      "args": [
        "alpha",
        "beta"
      ],
      "kind": "rel_fact",
      "relation": "inside"
    },
    {
      "args": [
        "beta",
        "gamma"
      ],
      "kind": "rel_fact",
      "relation": "inside"
    },
    {
      "args": [
        "gamma",
        "delta"
      ],
      "kind": "rel_fact",
      "relation": "inside"
    },
    {
      "args": [
        "eps",
        "gamma"
      ],
      "kind": "rel_fact",
      "note": "distractor",
      "relation": "inside"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "inside"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "inside"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "inside"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    }
  ],
  "query": {
    "args": [
      "dot",
      "delta"
    ],
    "relation": "inside"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Nested-container transitivity puzzles exist in public corpora; the abstract container labels and the tail-attached distractor make verbatim retrieval unlikely.
AMBIGUITY_RISK: Low. 'Inside' is treated strictly as stated; no physical intuition is required.
STRUCTURAL_UNIQUENESS_RATIONALE: A five-container nesting chain whose distractor attaches INTO the chain (eps inside gamma) rather than standing apart; the query spans four transitive steps and the distractor shares a node with the chain.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Spatial-containment language must be parsed relationally; a literal 'inside' reading without transitive composition would mask the capability.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Nested-container transitivity puzzles exist in public corpora; the abstract container labels and the tail-attached distractor make verbatim retrieval unlikely.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-005
PROPOSED_REASONING_FAMILY: transitive-relational
STRUCTURAL_SIGNATURE: 5-entity main chain + two fully detached distractor pairs, 9 entities, both order rules, 4-step query
PREMISES:
1. The ka stands north of the lu.
2. The lu stands north of the mi.
3. The mi stands north of the no.
4. The no stands north of the pa.
5. The sa stands north of the ta.
6. The ub stands north of the vc.
7. For any three objects, if the first stands north of the second and the second stands north of the third, then the first stands north of the third.
8. For any two objects, if the first stands north of the second, then the second does not stand north of the first.
QUESTION: Is the ka north of the pa? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A four-step chain derivation through the main sequence while ignoring two detached distractor pairs.
INTENDED_CORRECT_ANSWER: Yes — the ka stands north of the pa.
DERIVATION:
1. From premises 1 and 2, by transitivity (premise 7): the ka stands north of the mi.
2. From that result and premise 3: the ka stands north of the no.
3. From that result and premise 4: the ka stands north of the pa.
4. The answer is yes. (The detached pairs in premises 5 and 6 do not touch any chain member.)
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the ka stands north of the pa
FORBIDDEN_SHORTCUTS:
- Do not treat the detached pairs (sa, ta) and (ub, vc) as part of the chain.
- Do not answer from mention order; the chain must be derived step by step.
FORMAL:
```json
{
  "entities": [
    "ka",
    "lu",
    "mi",
    "no",
    "pa",
    "sa",
    "ta",
    "ub",
    "vc"
  ],
  "premises": [
    {
      "args": [
        "ka",
        "lu"
      ],
      "kind": "rel_fact",
      "relation": "north_of"
    },
    {
      "args": [
        "lu",
        "mi"
      ],
      "kind": "rel_fact",
      "relation": "north_of"
    },
    {
      "args": [
        "mi",
        "no"
      ],
      "kind": "rel_fact",
      "relation": "north_of"
    },
    {
      "args": [
        "no",
        "pa"
      ],
      "kind": "rel_fact",
      "relation": "north_of"
    },
    {
      "args": [
        "sa",
        "ta"
      ],
      "kind": "rel_fact",
      "note": "distractor",
      "relation": "north_of"
    },
    {
      "args": [
        "ub",
        "vc"
      ],
      "kind": "rel_fact",
      "note": "distractor",
      "relation": "north_of"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "north_of"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "north_of"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "north_of"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "north_of"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "y",
          "x"
        ],
        "negated": true,
        "relation": "north_of"
      },
      "vars": [
        "x",
        "y"
      ]
    }
  ],
  "query": {
    "args": [
      "ka",
      "pa"
    ],
    "relation": "north_of"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: DEEP
RETRIEVAL_RISK: North-of arrangement puzzles are common in public corpora, but this instance is a bare minimal chain with invented two-letter entities and no map or geometry, reducing retrieval likelihood.
AMBIGUITY_RISK: Low. The relation is a strict order and both rules are explicit.
STRUCTURAL_UNIQUENESS_RATIONALE: Nine entities: a five-member main chain plus two fully detached distractor pairs, with both order rules present and a four-step query; the distractor structure (two isolated pairs) is distinct from the tail-attached distractor of the nesting case.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Systems without robust working memory over long premise lists may lose the chain; this is a load property of the representation, not proof of missing order-reasoning capability.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: North-of arrangement puzzles are common in public corpora, but this instance is a bare minimal chain with invented two-letter entities and no map or geometry, reducing retrieval likelihood.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-006
PROPOSED_REASONING_FAMILY: conditional-chaining
STRUCTURAL_SIGNATURE: 3-link implication chain + true antecedent fact, forward query on final consequent
PREMISES:
1. If the beacon is lit, then the gate opens.
2. If the gate opens, then the horn sounds.
3. If the horn sounds, then the bridge lowers.
4. The beacon is lit.
QUESTION: Does the bridge lower? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A three-step modus-ponens chain from the stated antecedent to the final consequent.
INTENDED_CORRECT_ANSWER: Yes — the bridge lowers.
DERIVATION:
1. From premise 4 and premise 1 (modus ponens): the gate opens.
2. From that result and premise 2: the horn sounds.
3. From that result and premise 3: the bridge lowers.
4. The answer is yes.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the bridge lowers
FORBIDDEN_SHORTCUTS:
- Do not conclude from the mere presence of the rules without using premise 4.
- Do not invoke world knowledge about beacons, gates, or bridges; only the stated conditionals may be used.
FORMAL:
```json
{
  "premises": [
    {
      "if": [
        "beacon"
      ],
      "kind": "impl",
      "then": "gate"
    },
    {
      "if": [
        "gate"
      ],
      "kind": "impl",
      "then": "horn"
    },
    {
      "if": [
        "horn"
      ],
      "kind": "impl",
      "then": "bridge"
    },
    {
      "kind": "prop_fact",
      "prop": "beacon",
      "value": true
    }
  ],
  "props": [
    "beacon",
    "gate",
    "horn",
    "bridge"
  ],
  "query": {
    "prop": "bridge",
    "value": true
  },
  "semantics": "propositional-truth-table"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Chained conditionals with a lit initial condition are a standard logic-exercise shape; the specific beacon/gate/horn/bridge content is invented for this case.
AMBIGUITY_RISK: Low. The conditionals are one-directional and the antecedent is stated as fact.
STRUCTURAL_UNIQUENESS_RATIONALE: A pure three-link forward chain with a positive root fact and a query on the terminal consequent; no contrapositive step, no distractor rule, and no negated fact anywhere in the set.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: A system that reads conditionals as biconditionals can still answer this case correctly; the representation cannot distinguish the two readings here, which is a property of the case, not of the system.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Chained conditionals with a lit initial condition are a standard logic-exercise shape; the specific beacon/gate/horn/bridge content is invented for this case.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-007
PROPOSED_REASONING_FAMILY: conditional-chaining
STRUCTURAL_SIGNATURE: 2-link implication chain + negated final consequent, modus-tollens query on first antecedent
PREMISES:
1. If the mill turns, then the well fills.
2. If the well fills, then the lantern glows.
3. The lantern does not glow.
QUESTION: Does the mill turn? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A two-step contrapositive (modus tollens) derivation that refutes the chain's first antecedent.
INTENDED_CORRECT_ANSWER: No — the mill does not turn.
DERIVATION:
1. Suppose the mill turned. Then by premise 1 the well would fill, and by premise 2 the lantern would glow.
2. Premise 3 states the lantern does not glow, so the supposition is impossible.
3. Therefore the mill does not turn: the queried statement is refuted and the answer is no.
GROUND_TRUTH_CLASS: CONTRADICTED
GROUND_TRUTH_STATEMENT: the mill turns
FORBIDDEN_SHORTCUTS:
- Do not answer 'cannot be determined' — the premises rule the queried statement out.
- Do not treat the conditionals as evidence about what happens when the lantern glows; only the forward directions plus modus tollens are used.
FORMAL:
```json
{
  "premises": [
    {
      "if": [
        "mill"
      ],
      "kind": "impl",
      "then": "well"
    },
    {
      "if": [
        "well"
      ],
      "kind": "impl",
      "then": "glow"
    },
    {
      "kind": "prop_fact",
      "prop": "glow",
      "value": false
    }
  ],
  "props": [
    "mill",
    "well",
    "glow"
  ],
  "query": {
    "prop": "mill",
    "value": true
  },
  "semantics": "propositional-truth-table"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Modus-tollens chains are common in logic teaching material; the mill/well/lantern content is invented and minimal.
AMBIGUITY_RISK: Low. The negated fact is stated directly and the chain is linear.
STRUCTURAL_UNIQUENESS_RATIONALE: A two-link chain queried at its root with only the terminal consequent negated; the answer requires exactly two contrapositive steps and nothing else, with no distractor premises.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Negation handling in natural language ('does not glow') is representation-sensitive; misparsing the negated fact would corrupt the contrapositive path.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Modus-tollens chains are common in logic teaching material; the mill/well/lantern content is invented and minimal.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-008
PROPOSED_REASONING_FAMILY: conditional-chaining
STRUCTURAL_SIGNATURE: single implication + true consequent + unconnected distractor rule, converse-fallacy query
PREMISES:
1. If the tide rises, then the bell rings.
2. The bell rings.
3. If the bell rings, then the dock is wet.
QUESTION: Did the tide rise? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Resistance to the converse fallacy: the stated consequent does not establish the antecedent, and the answer is a reported indeterminacy.
INTENDED_CORRECT_ANSWER: Cannot be determined — the bell ringing does not establish that the tide rose; the conditional runs one way, and other causes of the bell ringing are not excluded.
DERIVATION:
1. Premise 1 licenses only: tide rises → bell rings. It does not license bell rings → tide rises.
2. Premise 2 states the bell rings; this is compatible with the tide having risen and with it not having risen.
3. No premise states or implies the reverse direction, and nothing excludes other causes of the ringing.
4. The answer is cannot be determined. (Premise 3 additionally implies the dock is wet, but bears on the tide only through the bell, which is already given.)
GROUND_TRUTH_CLASS: INDETERMINATE
GROUND_TRUTH_STATEMENT: the tide rose
FORBIDDEN_SHORTCUTS:
- Do not apply the converse of premise 1.
- Do not use plausibility about tides and bells; only the stated conditionals count.
FORMAL:
```json
{
  "premises": [
    {
      "if": [
        "tide"
      ],
      "kind": "impl",
      "then": "bell"
    },
    {
      "kind": "prop_fact",
      "prop": "bell",
      "value": true
    },
    {
      "if": [
        "bell"
      ],
      "kind": "impl",
      "then": "dock"
    }
  ],
  "props": [
    "tide",
    "bell",
    "dock"
  ],
  "query": {
    "prop": "tide",
    "value": true
  },
  "semantics": "propositional-truth-table"
}
```
DIFFICULTY: SHALLOW
RETRIEVAL_RISK: Affirming-the-consequent probes are widespread in evaluation corpora; the invented tide/bell/dock content keeps this instance distinct from named benchmarks.
AMBIGUITY_RISK: Low. The one-directional conditional is stated plainly and the question allows abstention.
STRUCTURAL_UNIQUENESS_RATIONALE: The smallest converse-fallacy trap with an attached distractor rule that derives an unrelated fact (the wet dock), testing whether the system confuses derivable-but-irrelevant content with an answer to the query.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Systems trained to always resolve a query may guess rather than abstain; the representation offers the abstention option without signaling that it is correct here.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Affirming-the-consequent probes are widespread in evaluation corpora; the invented tide/bell/dock content keeps this instance distinct from named benchmarks.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-009
PROPOSED_REASONING_FAMILY: conditional-chaining
STRUCTURAL_SIGNATURE: single implication + negated antecedent + downstream distractor rule, inverse-fallacy query
PREMISES:
1. If the switch is flipped, then the motor runs.
2. The switch is not flipped.
3. If the motor runs, then the lamp glows.
QUESTION: Does the motor run? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Resistance to the inverse fallacy (denial of the antecedent): a sufficient condition's failure does not establish the outcome's failure.
INTENDED_CORRECT_ANSWER: Cannot be determined — the flipped switch is stated as sufficient for the motor running, not necessary; the motor may run for unstated reasons.
DERIVATION:
1. Premise 1 gives: switch flipped → motor runs. It does not give: switch not flipped → motor not running.
2. Premise 2 states the switch is not flipped; assignments in which the motor runs (with the lamp glowing by premise 3) and assignments in which it does not run both satisfy all premises.
3. Neither the queried statement nor its negation is derivable.
4. The answer is cannot be determined.
GROUND_TRUTH_CLASS: INDETERMINATE
GROUND_TRUTH_STATEMENT: the motor runs
FORBIDDEN_SHORTCUTS:
- Do not apply the inverse of premise 1.
- Do not treat the switch as the only cause of the motor running.
FORMAL:
```json
{
  "premises": [
    {
      "if": [
        "switch"
      ],
      "kind": "impl",
      "then": "motor"
    },
    {
      "kind": "prop_fact",
      "prop": "switch",
      "value": false
    },
    {
      "if": [
        "motor"
      ],
      "kind": "impl",
      "then": "lamp"
    }
  ],
  "props": [
    "switch",
    "motor",
    "lamp"
  ],
  "query": {
    "prop": "motor",
    "value": true
  },
  "semantics": "propositional-truth-table"
}
```
DIFFICULTY: SHALLOW
RETRIEVAL_RISK: Denial-of-the-antecedent probes are standard; the switch/motor/lamp content is invented and the distractor rule gives the case a distinct downstream structure.
AMBIGUITY_RISK: Low. The conditional direction and the negated antecedent are both explicit.
STRUCTURAL_UNIQUENESS_RATIONALE: The inverse-fallacy companion to the converse-fallacy case: here the negated input is given and the query asks about the outcome, with a downstream rule whose own condition is exactly the queried undetermined proposition.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: The distractor rule's condition being the query itself invites chain-completion behavior; this is a representational pressure, not a capability verdict.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Denial-of-the-antecedent probes are standard; the switch/motor/lamp content is invented and the distractor rule gives the case a distinct downstream structure.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-010
PROPOSED_REASONING_FAMILY: conditional-chaining
STRUCTURAL_SIGNATURE: 3-link implication chain with one link beyond the query + negated middle consequent, root query refuted
PREMISES:
1. If the rain falls, then the soil dampens.
2. If the soil dampens, then the seeds sprout.
3. If the seeds sprout, then the field turns green.
4. The seeds did not sprout.
QUESTION: Did the rain fall? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A two-step contrapositive refutation at the chain root, with a third rule present that extends beyond the query and is not needed.
INTENDED_CORRECT_ANSWER: No — the rain did not fall.
DERIVATION:
1. Suppose the rain fell. By premise 1 the soil would dampen, and by premise 2 the seeds would sprout — contradicting premise 4.
2. Hence the rain did not fall: the queried statement is refuted.
3. Premise 3 (about the field turning green) is not needed for this conclusion.
GROUND_TRUTH_CLASS: CONTRADICTED
GROUND_TRUTH_STATEMENT: the rain fell
FORBIDDEN_SHORTCUTS:
- Do not use the state of the field (premise 3's consequent) to reason back to the rain; the direction is wrong and the premise is not needed.
- Do not answer 'cannot be determined' — the chain plus premise 4 refutes the query.
FORMAL:
```json
{
  "premises": [
    {
      "if": [
        "rain"
      ],
      "kind": "impl",
      "then": "soil"
    },
    {
      "if": [
        "soil"
      ],
      "kind": "impl",
      "then": "sprout"
    },
    {
      "if": [
        "sprout"
      ],
      "kind": "impl",
      "then": "green"
    },
    {
      "kind": "prop_fact",
      "prop": "sprout",
      "value": false
    }
  ],
  "props": [
    "rain",
    "soil",
    "sprout",
    "green"
  ],
  "query": {
    "prop": "rain",
    "value": true
  },
  "semantics": "propositional-truth-table"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Rain/soil/seeds chains resemble common causal-reasoning exercises; the specific three-rule shape with a negated middle outcome is composed for this case.
AMBIGUITY_RISK: Low. All rules are one-directional and the negated fact is direct.
STRUCTURAL_UNIQUENESS_RATIONALE: A three-link chain whose negated fact sits at the middle outcome and whose query is the root, with one rule extending beyond the query's needs — deeper than the two-link modus-tollens case and directionally different from the forward-chain case.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Causal-sounding language ('rain falls, soil dampens') may invite world-knowledge shortcuts; the representation cannot prevent this, only the forbidden-shortcuts note flags it.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Rain/soil/seeds chains resemble common causal-reasoning exercises; the specific three-rule shape with a negated middle outcome is composed for this case.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-011
PROPOSED_REASONING_FAMILY: consistency-contradiction
STRUCTURAL_SIGNATURE: 3-statement universal + instance + negation conflict, joint-consistency query
PREMISES:
1. Every fep is a lum.
2. The zor is a fep.
3. The zor is not a lum.
QUESTION: Are the three numbered statements mutually consistent? Answer with: yes or no.
EXPECTED_PROPERTY: A joint-consistency verdict derived by instantiating the universal statement and detecting a direct conflict.
INTENDED_CORRECT_ANSWER: No — the statements are jointly inconsistent.
DERIVATION:
1. From premises 1 and 2: the zor is a lum.
2. Premise 3 states the zor is not a lum.
3. The conjunction asserts both a statement and its negation about the zor, so no assignment satisfies all three.
4. The answer is no.
GROUND_TRUTH_CLASS: CONTRADICTED
GROUND_TRUTH_STATEMENT: the three statements are mutually consistent
FORBIDDEN_SHORTCUTS:
- Do not weaken 'every' to 'most' to rescue consistency.
- Do not answer about pairwise consistency; the question is joint consistency.
FORMAL:
```json
{
  "premises": [
    {
      "if": [
        "zor_fep"
      ],
      "kind": "impl",
      "then": "zor_lum"
    },
    {
      "kind": "prop_fact",
      "prop": "zor_fep",
      "value": true
    },
    {
      "kind": "prop_fact",
      "prop": "zor_lum",
      "value": false
    }
  ],
  "props": [
    "zor_fep",
    "zor_lum"
  ],
  "query": {
    "kind": "consistency"
  },
  "semantics": "propositional-truth-table"
}
```
DIFFICULTY: SHALLOW
RETRIEVAL_RISK: This is the smallest syllogistic inconsistency shape and is very common in public corpora; it is retained deliberately as the family's baseline case, with invented vocabulary preventing verbatim retrieval of a named-benchmark item.
AMBIGUITY_RISK: Low. The universal is unqualified and the instance statements are direct.
STRUCTURAL_UNIQUENESS_RATIONALE: The minimal honest inconsistency demonstration: one universal, one instance, one negation; every other family-3 case builds on deeper mechanisms (closure cycles, repair counting).
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Systems may answer from surface pattern recognition of 'all/some/no' puzzles rather than actual consistency checking; the representation cannot separate the two mechanisms.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: This is the smallest syllogistic inconsistency shape and is very common in public corpora; it is retained deliberately as the family's baseline case, with invented vocabulary preventing verbatim retrieval of a named-benchmark item.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-012
PROPOSED_REASONING_FAMILY: consistency-contradiction
STRUCTURAL_SIGNATURE: 6-statement set with quantifier pairs whose converse misreadings fake a conflict, joint-consistency query
PREMISES:
1. The pau is a wug.
2. Every wug is a tave.
3. No rix is a tave.
4. The pau is not a rix.
5. The dov is a tave.
6. The dov is not a wug.
QUESTION: Are the six numbered statements mutually consistent? Answer with: yes or no.
EXPECTED_PROPERTY: A joint-consistency verdict that survives two quantified statements whose converses would falsely suggest a conflict.
INTENDED_CORRECT_ANSWER: Yes — the statements are mutually consistent.
DERIVATION:
1. From premises 1 and 2: the pau is a tave. Premise 4 (the pau is not a rix) is compatible with premise 3, which only excludes rixes from being taves.
2. Premises 5 and 6 describe the dov as a tave that is not a wug. Only wugs must be taves (premise 2); nothing requires taves to be wugs, so no conflict arises.
3. An assignment satisfies all six (pau: wug, tave, not rix; dov: tave, not wug).
4. The answer is yes.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the six statements are mutually consistent
FORBIDDEN_SHORTCUTS:
- Do not read premise 2 as its converse ('every tave is a wug') — that would wrongly conflict with premise 6.
- Do not treat 'no rix is a tave' as 'no tave is a rix' plus an equivalence claim; the stated direction already suffices.
FORMAL:
```json
{
  "premises": [
    {
      "kind": "prop_fact",
      "prop": "pau_wug",
      "value": true
    },
    {
      "if": [
        "pau_wug"
      ],
      "kind": "impl",
      "then": "pau_tave"
    },
    {
      "if": [
        "pau_rix"
      ],
      "kind": "impl",
      "then": "pau_tave",
      "then_value": false
    },
    {
      "kind": "prop_fact",
      "prop": "pau_rix",
      "value": false
    },
    {
      "kind": "prop_fact",
      "prop": "dov_tave",
      "value": true
    },
    {
      "kind": "prop_fact",
      "prop": "dov_wug",
      "value": false
    }
  ],
  "props": [
    "pau_wug",
    "pau_tave",
    "pau_rix",
    "dov_tave",
    "dov_wug"
  ],
  "query": {
    "kind": "consistency"
  },
  "semantics": "propositional-truth-table"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Multi-statement category sets with converse traps appear in aptitude material; the invented wug/tave/rix/dov vocabulary and the six-statement shape are composed for this case.
AMBIGUITY_RISK: Moderate-low: the only risk is the converse misreading itself, which is the phenomenon under test, not an unintended ambiguity.
STRUCTURAL_UNIQUENESS_RATIONALE: A six-statement consistent set with two quantified statements whose converses would manufacture a fake conflict; the consistency verdict requires resisting both misreadings at once.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Quantifier wording ('every', 'no') is where the representation pressure concentrates; a misparse at these two words flips the verdict without any reasoning defect.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Multi-statement category sets with converse traps appear in aptitude material; the invented wug/tave/rix/dov vocabulary and the six-statement shape are composed for this case.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-013
PROPOSED_REASONING_FAMILY: consistency-contradiction
STRUCTURAL_SIGNATURE: 3-fact weight cycle + transitivity + asymmetry, inconsistency visible only under closure
PREMISES:
1. The fel is heavier than the gam.
2. The gam is heavier than the hup.
3. The hup is heavier than the fel.
4. For any three objects, if the first is heavier than the second and the second is heavier than the third, then the first is heavier than the third.
5. For any two objects, if the first is heavier than the second, then the second is not heavier than the first.
QUESTION: Are the five numbered statements mutually consistent? Answer with: yes or no.
EXPECTED_PROPERTY: A consistency verdict that requires deriving a closure fact before the conflict appears — no adjacent pair conflicts directly.
INTENDED_CORRECT_ANSWER: No — the statements are jointly inconsistent.
DERIVATION:
1. From premises 1 and 2 with transitivity (premise 4): the fel is heavier than the hup.
2. Premise 3 states the hup is heavier than the fel; by asymmetry (premise 5) applied to premise 3, the fel is not heavier than the hup.
3. Both a statement and its negation about the same pair are derivable, so no model satisfies all five.
4. The answer is no.
GROUND_TRUTH_CLASS: CONTRADICTED
GROUND_TRUTH_STATEMENT: the five statements are mutually consistent
FORBIDDEN_SHORTCUTS:
- Do not test only adjacent pairs; the conflict emerges only through the three-step cycle closure.
- Do not drop asymmetry (premise 5) from the check; the refutation uses it.
FORMAL:
```json
{
  "entities": [
    "fel",
    "gam",
    "hup"
  ],
  "premises": [
    {
      "args": [
        "fel",
        "gam"
      ],
      "kind": "rel_fact",
      "relation": "heavier"
    },
    {
      "args": [
        "gam",
        "hup"
      ],
      "kind": "rel_fact",
      "relation": "heavier"
    },
    {
      "args": [
        "hup",
        "fel"
      ],
      "kind": "rel_fact",
      "relation": "heavier"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "heavier"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "heavier"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "heavier"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "heavier"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "y",
          "x"
        ],
        "negated": true,
        "relation": "heavier"
      },
      "vars": [
        "x",
        "y"
      ]
    }
  ],
  "query": {
    "kind": "consistency"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Cyclic-order inconsistency is a known deep shape but less common than direct conflicts; the invented entities and the explicit rule pair make this instance self-contained.
AMBIGUITY_RISK: Low. The rules are stated and the cycle is complete.
STRUCTURAL_UNIQUENESS_RATIONALE: A three-cycle whose inconsistency is invisible pairwise and appears only under transitive closure plus asymmetry — the mechanism is derivation, not statement collision, distinguishing it from the direct-conflict baseline case.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: The conflict requires two composed steps; systems limited to pairwise checking will misreport consistency — a depth property of the case, not a parsing defect.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Cyclic-order inconsistency is a known deep shape but less common than direct conflicts; the invented entities and the explicit rule pair make this instance self-contained.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-014
PROPOSED_REASONING_FAMILY: consistency-contradiction
STRUCTURAL_SIGNATURE: 2 chained conditionals + 2 negated facts, surface tension without conflict, consistency query
PREMISES:
1. If the paz is a ryn, then the paz is a tobe.
2. The paz is not a tobe.
3. If the paz is a tobe, then the paz is a vex.
4. The paz is not a vex.
QUESTION: Are the four numbered statements mutually consistent? Answer with: yes or no.
EXPECTED_PROPERTY: A consistency verdict that survives surface tension: negated facts that overlap with rule consequents and antecedents without producing any conflict.
INTENDED_CORRECT_ANSWER: Yes — the statements are mutually consistent.
DERIVATION:
1. Premise 2 fixes the paz as not a tobe; premise 4 fixes the paz as not a vex.
2. Premise 1 is then satisfied whether or not the paz is a ryn (its consequent is required only when the paz is a ryn; additionally, modus tollens yields that the paz is not a ryn, which is itself consistent).
3. Premise 3 is vacuous with the paz not a tobe, and premise 4 is an independent fact.
4. An assignment satisfies all four (paz: not ryn, not tobe, not vex).
5. The answer is yes.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the four statements are mutually consistent
FORBIDDEN_SHORTCUTS:
- Do not read the conditionals as biconditionals.
- Do not mistake 'not a tobe' for contradicting the mere existence of rules mentioning tobe.
FORMAL:
```json
{
  "premises": [
    {
      "if": [
        "paz_ryn"
      ],
      "kind": "impl",
      "then": "paz_tobe"
    },
    {
      "kind": "prop_fact",
      "prop": "paz_tobe",
      "value": false
    },
    {
      "if": [
        "paz_tobe"
      ],
      "kind": "impl",
      "then": "paz_vex"
    },
    {
      "kind": "prop_fact",
      "prop": "paz_vex",
      "value": false
    }
  ],
  "props": [
    "paz_ryn",
    "paz_tobe",
    "paz_vex"
  ],
  "query": {
    "kind": "consistency"
  },
  "semantics": "propositional-truth-table"
}
```
DIFFICULTY: SHALLOW
RETRIEVAL_RISK: Small propositional sets with vacuous conditionals are common in teaching material; the invented paz/ryn/tobe/vex vocabulary is composed for this case.
AMBIGUITY_RISK: Low. The facts are direct negations and the rules are one-directional.
STRUCTURAL_UNIQUENESS_RATIONALE: A four-statement set in which every rule's antecedent or consequent is contradicted by a fact, yet the set is consistent because the rules fire vacuously — the mirror image of the direct-conflict case.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: The repeated 'not a tobe / rules about tobe' phrasing creates surface tension that purely lexical matching would misjudge as conflict.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Small propositional sets with vacuous conditionals are common in teaching material; the invented paz/ryn/tobe/vex vocabulary is composed for this case.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-015
PROPOSED_REASONING_FAMILY: consistency-contradiction
STRUCTURAL_SIGNATURE: 3-fact age cycle + detached pair + 2 order rules, repair-count query over six statements
PREMISES:
1. The wan is older than the xel.
2. The xel is older than the yim.
3. The yim is older than the wan.
4. The bex is older than the cav.
5. For any three objects, if the first is older than the second and the second is older than the third, then the first is older than the third.
6. For any two objects, if the first is older than the second, then the second is not older than the first.
QUESTION: Exactly how many of the six numbered statements could be individually removed so that the remaining five become mutually consistent? Answer with a number.
EXPECTED_PROPERTY: A repair-count verdict: each of the six single-removal scenarios must be evaluated on the remaining five statements, and the count (five) differs from both the statement total and the cycle size.
INTENDED_CORRECT_ANSWER: Five — every statement except statement 4 (the bex–cav pair).
DERIVATION:
1. With all six present: transitivity over premises 1–2 gives 'the wan is older than the yim', while premise 3 plus asymmetry gives 'the wan is not older than the yim' — inconsistent.
2. Removing statement 1, 2, or 3 breaks the only cycle; the remaining five are consistent in each case.
3. Removing statement 5 (transitivity): the three cycle facts plus asymmetry yield only reverses of stated pairs — no positive–negative collision — consistent.
4. Removing statement 6 (asymmetry): the facts and their transitive closure are all positive — consistent.
5. Removing statement 4 leaves the cycle intact — still inconsistent.
6. Exactly five single removals (statements 1, 2, 3, 5, 6) restore consistency.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: exactly five of the six statements are individually removable to restore consistency
FORBIDDEN_SHORTCUTS:
- Do not answer 'six' by assuming any removal helps — statement 4's removal leaves the cycle untouched.
- Each removal must be evaluated on the remaining five statements, not on intuition about cycles.
FORMAL:
```json
{
  "entities": [
    "wan",
    "xel",
    "yim",
    "bex",
    "cav"
  ],
  "premises": [
    {
      "args": [
        "wan",
        "xel"
      ],
      "kind": "rel_fact",
      "relation": "older"
    },
    {
      "args": [
        "xel",
        "yim"
      ],
      "kind": "rel_fact",
      "relation": "older"
    },
    {
      "args": [
        "yim",
        "wan"
      ],
      "kind": "rel_fact",
      "relation": "older"
    },
    {
      "args": [
        "bex",
        "cav"
      ],
      "kind": "rel_fact",
      "note": "distractor",
      "relation": "older"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "older"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "older"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "older"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "older"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "y",
          "x"
        ],
        "negated": true,
        "relation": "older"
      },
      "vars": [
        "x",
        "y"
      ]
    }
  ],
  "query": {
    "kind": "repair_count"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: DEEP
RETRIEVAL_RISK: Repair-count questions over cyclic rule sets are rare in public corpora compared to plain consistency questions; the specific six-statement shape with a detached pair is composed for this case.
AMBIGUITY_RISK: Moderate-low: 'how many could be individually removed' must be read as counting single removals, which the question states explicitly.
STRUCTURAL_UNIQUENESS_RATIONALE: A meta-level repair-count question over a three-cycle with a detached pair; the correct count (five) coincides with neither the statement total (six) nor the cycle size (three), and rule removals count alongside fact removals.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Counting questions demand exact enumeration under each removal; systems without systematic scenario evaluation will approximate, which the representation itself cannot force.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Repair-count questions over cyclic rule sets are rare in public corpora compared to plain consistency questions; the specific six-statement shape with a detached pair is composed for this case.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-016
PROPOSED_REASONING_FAMILY: relational-discrimination
STRUCTURAL_SIGNATURE: symmetric at-least pair + third-entity distractor + equality rule, strict query refuted
PREMISES:
1. The mir is at least as tall as the jek.
2. The jek is at least as tall as the mir.
3. The kel is taller than the mir.
4. For any two objects, if each is at least as tall as the other, then the two are equal in height.
5. For any two objects that are equal in height, the first is not taller than the second.
QUESTION: Is the mir taller than the jek? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A verdict that applies the equality rule to the symmetric at-least pair and thereby refutes the strict query; the third-entity premise must be recognized as irrelevant.
INTENDED_CORRECT_ANSWER: No — the mir is not taller than the jek.
DERIVATION:
1. From premises 1 and 2 with premise 4: the mir and the jek are equal in height.
2. By premise 5, the mir is therefore not taller than the jek.
3. The queried statement is refuted; the answer is no. (Premise 3, about the kel, is not needed.)
GROUND_TRUTH_CLASS: CONTRADICTED
GROUND_TRUTH_STATEMENT: the mir is taller than the jek
FORBIDDEN_SHORTCUTS:
- Do not conflate 'at least as tall' with 'taller' — the distinction is the point of the case.
- Do not use premise 3 (about the kel) to answer a question about the mir and the jek.
FORMAL:
```json
{
  "entities": [
    "mir",
    "jek",
    "kel"
  ],
  "premises": [
    {
      "args": [
        "mir",
        "jek"
      ],
      "kind": "rel_fact",
      "relation": "at_least"
    },
    {
      "args": [
        "jek",
        "mir"
      ],
      "kind": "rel_fact",
      "relation": "at_least"
    },
    {
      "args": [
        "kel",
        "mir"
      ],
      "kind": "rel_fact",
      "note": "distractor",
      "relation": "taller"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "at_least"
        },
        {
          "args": [
            "y",
            "x"
          ],
          "relation": "at_least"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "y"
        ],
        "relation": "equal"
      },
      "vars": [
        "x",
        "y"
      ]
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "equal"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "y"
        ],
        "negated": true,
        "relation": "taller"
      },
      "vars": [
        "x",
        "y"
      ]
    }
  ],
  "query": {
    "args": [
      "mir",
      "jek"
    ],
    "relation": "taller"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: At-least/taller discrimination is a standard logic-of-comparison exercise shape; the invented entities and the explicit bridge rule reduce verbatim retrieval likelihood.
AMBIGUITY_RISK: Low. Both relations are named consistently and the equality rule is stated.
STRUCTURAL_UNIQUENESS_RATIONALE: The equality rule fires on a symmetric at-least pair (two-step derivation) with a third-entity distractor present, distinguishing it from the minimal two-entity equality case and from pure strict-order chains.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: The phrase 'at least as tall' is where representational failure concentrates: systems that normalize it to 'taller' will answer contrary to their own capability.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: At-least/taller discrimination is a standard logic-of-comparison exercise shape; the invented entities and the explicit bridge rule reduce verbatim retrieval likelihood.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-017
PROPOSED_REASONING_FAMILY: relational-discrimination
STRUCTURAL_SIGNATURE: strict + non-strict mixed chain with widening rule before transitivity, non-strict query derivable
PREMISES:
1. The dov is heavier than the pel.
2. The pel is at least as heavy as the rus.
3. For any two objects, if the first is heavier than the second, then the first is at least as heavy as the second.
4. For any three objects, if the first is at least as heavy as the second and the second is at least as heavy as the third, then the first is at least as heavy as the third.
QUESTION: Is the dov at least as heavy as the rus? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A derivation that widens the strict relation to the non-strict one (premise 3) before chaining, ending in a non-strict conclusion.
INTENDED_CORRECT_ANSWER: Yes — the dov is at least as heavy as the rus.
DERIVATION:
1. From premise 1 with premise 3: the dov is at least as heavy as the pel.
2. From that result and premise 2, by transitivity (premise 4): the dov is at least as heavy as the rus.
3. The answer is yes.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the dov is at least as heavy as the rus
FORBIDDEN_SHORTCUTS:
- Do not skip the strict-to-non-strict step (premise 3); 'heavier than' must be explicitly widened before chaining.
- Do not answer about 'heavier than the rus' — the query is the non-strict relation.
FORMAL:
```json
{
  "entities": [
    "dov",
    "pel",
    "rus"
  ],
  "premises": [
    {
      "args": [
        "dov",
        "pel"
      ],
      "kind": "rel_fact",
      "relation": "heavier"
    },
    {
      "args": [
        "pel",
        "rus"
      ],
      "kind": "rel_fact",
      "relation": "at_least"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "heavier"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "y"
        ],
        "relation": "at_least"
      },
      "vars": [
        "x",
        "y"
      ]
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "at_least"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "at_least"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "at_least"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    }
  ],
  "query": {
    "args": [
      "dov",
      "rus"
    ],
    "relation": "at_least"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Mixed strict/non-strict chains are less common than pure chains; the invented entities and the two-rule shape are composed for this case.
AMBIGUITY_RISK: Low. Both relations are used exactly as named; the widening rule is explicit.
STRUCTURAL_UNIQUENESS_RATIONALE: A mixed strict/non-strict chain requiring one widening step before transitivity — the derivation shape (widen, then chain) is unique in the pool, and the query is deliberately the weaker relation.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: A system that treats 'heavier' and 'at least as heavy' as a single ordering vocabulary without applying the supplied bridge will produce an unlicensed conclusion.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Mixed strict/non-strict chains are less common than pure chains; the invented entities and the two-rule shape are composed for this case.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-018
PROPOSED_REASONING_FAMILY: relational-discrimination
STRUCTURAL_SIGNATURE: pure non-strict chain of 3 facts + transitivity only, strict query with no strictening rule
PREMISES:
1. The fab is at least as old as the gip.
2. The gip is at least as old as the hul.
3. The fab is at least as old as the hul.
4. For any three objects, if the first is at least as old as the second and the second is at least as old as the third, then the first is at least as old as the third.
QUESTION: Is the fab older than the hul? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Recognition that no rule licenses the strict relation from the non-strict one, producing a reported indeterminacy rather than a tightened conclusion.
INTENDED_CORRECT_ANSWER: Cannot be determined — the premises establish only the non-strict relation; both equality and strict inequality between the fab and the hul are compatible with them.
DERIVATION:
1. Premise 3 already states the non-strict relation; transitivity (premise 4) adds nothing stronger.
2. No premise supplies a rule from 'at least as old' to 'older' (there is no strictening rule), and no premise excludes equality.
3. Neither 'the fab is older than the hul' nor its negation is derivable.
4. The answer is cannot be determined.
GROUND_TRUTH_CLASS: INDETERMINATE
GROUND_TRUTH_STATEMENT: the fab is older than the hul
FORBIDDEN_SHORTCUTS:
- Do not tighten 'at least as old' into 'older' — no rule licenses the strict direction.
- Do not answer 'yes' because the chained premises suggest a descent; the non-strict relation never sharpens.
FORMAL:
```json
{
  "entities": [
    "fab",
    "gip",
    "hul"
  ],
  "premises": [
    {
      "args": [
        "fab",
        "gip"
      ],
      "kind": "rel_fact",
      "relation": "at_least"
    },
    {
      "args": [
        "gip",
        "hul"
      ],
      "kind": "rel_fact",
      "relation": "at_least"
    },
    {
      "args": [
        "fab",
        "hul"
      ],
      "kind": "rel_fact",
      "relation": "at_least"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "at_least"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "at_least"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "at_least"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    }
  ],
  "query": {
    "args": [
      "fab",
      "hul"
    ],
    "relation": "older"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Non-strict chains with strict queries are a known calibrated-abstention shape but not a named benchmark pattern; the invented entities keep this instance distinct.
AMBIGUITY_RISK: Low. The question offers abstention and the missing-rule mechanism is clean.
STRUCTURAL_UNIQUENESS_RATIONALE: The mirror of the widening case: here the strictening rule is deliberately absent, and the abstention arises from the strict/non-strict boundary itself rather than from broken chains or fallacy traps.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Transitive-completion habits push toward 'yes'; the representation cannot signal that the strict reading is unlicensed — that is precisely the phenomenon under test.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Non-strict chains with strict queries are a known calibrated-abstention shape but not a named benchmark pattern; the invented entities keep this instance distinct.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-019
PROPOSED_REASONING_FAMILY: relational-discrimination
STRUCTURAL_SIGNATURE: parent-to-ancestor bridge + ancestor transitivity + depth-extending distractor, general-relation query derivable
PREMISES:
1. The ono is a parent of the pye.
2. The pye is a parent of the qas.
3. Every parent of someone is an ancestor of that person.
4. For any three persons, if the first is an ancestor of the second and the second is an ancestor of the third, then the first is an ancestor of the third.
5. The qas is a parent of the rul.
QUESTION: Is the ono an ancestor of the qas? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A two-step derivation using the specific-to-general bridge rule and transitivity of the general relation, with the deeper distractor link unused.
INTENDED_CORRECT_ANSWER: Yes — the ono is an ancestor of the qas.
DERIVATION:
1. From premise 1 with premise 3: the ono is an ancestor of the pye.
2. From premise 2 with premise 3: the pye is an ancestor of the qas.
3. From those two results with premise 4: the ono is an ancestor of the qas.
4. The answer is yes. (Premise 5 extends the line to the rul but is not needed.)
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the ono is an ancestor of the qas
FORBIDDEN_SHORTCUTS:
- Do not collapse 'parent' and 'ancestor' — the bridge rule (premise 3) must be used explicitly.
- Do not infer 'the ono is a parent of the qas'; only the ancestor relation follows.
FORMAL:
```json
{
  "entities": [
    "ono",
    "pye",
    "qas",
    "rul"
  ],
  "premises": [
    {
      "args": [
        "ono",
        "pye"
      ],
      "kind": "rel_fact",
      "relation": "parent"
    },
    {
      "args": [
        "pye",
        "qas"
      ],
      "kind": "rel_fact",
      "relation": "parent"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "parent"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "y"
        ],
        "relation": "ancestor"
      },
      "vars": [
        "x",
        "y"
      ]
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "ancestor"
        },
        {
          "args": [
            "y",
            "z"
          ],
          "relation": "ancestor"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "z"
        ],
        "relation": "ancestor"
      },
      "vars": [
        "x",
        "y",
        "z"
      ]
    },
    {
      "args": [
        "qas",
        "rul"
      ],
      "kind": "rel_fact",
      "note": "distractor",
      "relation": "parent"
    }
  ],
  "query": {
    "args": [
      "ono",
      "qas"
    ],
    "relation": "ancestor"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Kinship-bridge reasoning appears in logic textbooks; the invented names (ono, pye, qas, rul) and the two-rule shape keep this instance self-contained.
AMBIGUITY_RISK: Low. Parent and ancestor are defined by the stated rules only.
STRUCTURAL_UNIQUENESS_RATIONALE: A specific-to-general bridge rule composed with transitivity of the general relation, plus a depth-extending distractor: the discrimination is between relation levels, not between strictness readings.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Kinship vocabulary carries strong world priors; systems may substitute cultural defaults for the stated bridge rule — a representation effect, disclosed here rather than measured.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Kinship-bridge reasoning appears in logic textbooks; the invented names (ono, pye, qas, rul) and the two-rule shape keep this instance self-contained.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-020
PROPOSED_REASONING_FAMILY: relational-discrimination
STRUCTURAL_SIGNATURE: minimal 2-entity equality fact + equality-to-not-strict rule, strict query refuted in one step
PREMISES:
1. The sab and the tek are equal in weight.
2. For any two objects, if the first and the second are equal in weight, then the first is not heavier than the second.
QUESTION: Is the sab heavier than the tek? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: A one-step application of the equality-to-not-strict rule to a stated equality, refuting the strict query.
INTENDED_CORRECT_ANSWER: No — the sab is not heavier than the tek.
DERIVATION:
1. Premise 1 states the two objects are equal in weight.
2. Premise 2 applied to that fact: the sab is not heavier than the tek.
3. The queried statement is refuted; the answer is no.
GROUND_TRUTH_CLASS: CONTRADICTED
GROUND_TRUTH_STATEMENT: the sab is heavier than the tek
FORBIDDEN_SHORTCUTS:
- Do not read 'equal in weight' loosely as 'close in weight', which would leave the question open.
- Do not ignore premise 2; without it the equality would not by itself answer a strict-weight question.
FORMAL:
```json
{
  "entities": [
    "sab",
    "tek"
  ],
  "premises": [
    {
      "args": [
        "sab",
        "tek"
      ],
      "kind": "rel_fact",
      "relation": "equal_weight"
    },
    {
      "if": [
        {
          "args": [
            "x",
            "y"
          ],
          "relation": "equal_weight"
        }
      ],
      "kind": "rel_rule",
      "then": {
        "args": [
          "x",
          "y"
        ],
        "negated": true,
        "relation": "heavier"
      },
      "vars": [
        "x",
        "y"
      ]
    }
  ],
  "query": {
    "args": [
      "sab",
      "tek"
    ],
    "relation": "heavier"
  },
  "semantics": "relational-closure"
}
```
DIFFICULTY: SHALLOW
RETRIEVAL_RISK: Minimal equality/strictness probes are common in teaching material; this is the family's baseline case and its two-premise shape is the smallest honest instance of the phenomenon.
AMBIGUITY_RISK: Low. The equality is stated as fact and the rule is direct.
STRUCTURAL_UNIQUENESS_RATIONALE: The smallest discrimination case in the pool: one equality fact, one boundary rule, one refuted strict query — the deliberate floor of the family, against which the equality-rule and widening cases are the deeper variants.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Trivially parseable; representational failure here would indicate a basic comparison-vocabulary defect rather than a reasoning limitation.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Minimal equality/strictness probes are common in teaching material; this is the family's baseline case and its two-premise shape is the smallest honest instance of the phenomenon.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-021
PROPOSED_REASONING_FAMILY: constraint-quantitative
STRUCTURAL_SIGNATURE: 3x3 bijection with one exclusion + one direct assignment, last-slot query with unique solution
PREMISES:
1. Three pods — the av, the ba, and the cu — each hold exactly one gem, and no two pods hold the same gem.
2. The three available gems are the opal, the rust, and the sage.
3. The av does not hold the opal.
4. The ba holds the rust.
QUESTION: Which gem does the cu hold? Answer with exactly one of: opal, rust, sage, or cannot be determined.
EXPECTED_PROPERTY: A unique assignment derived by elimination, with the queried slot forced by the no-two-same rule.
INTENDED_CORRECT_ANSWER: The opal.
DERIVATION:
1. From premise 4, the rust is held by the ba; by premise 1 no other pod holds it.
2. From premise 3, the av holds neither the opal nor (by premise 1) the rust; the only remaining gem for the av is the sage.
3. The only gem left for the cu is the opal.
4. The assignment is unique: av = sage, ba = rust, cu = opal.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the cu holds the opal
FORBIDDEN_SHORTCUTS:
- Do not assign gems by the order in which the pods are named.
- The elimination must use the no-two-same rule (premise 1); without it the conclusion would not follow.
FORMAL:
```json
{
  "domains": {
    "av": [
      "opal",
      "rust",
      "sage"
    ],
    "ba": [
      "opal",
      "rust",
      "sage"
    ],
    "cu": [
      "opal",
      "rust",
      "sage"
    ]
  },
  "premises": [
    {
      "kind": "all_different",
      "vars": [
        "av",
        "ba",
        "cu"
      ]
    },
    {
      "kind": "not_equal",
      "value": "opal",
      "var": "av"
    },
    {
      "kind": "equals",
      "value": "rust",
      "var": "ba"
    }
  ],
  "query": {
    "kind": "value_of",
    "var": "cu"
  },
  "semantics": "constraint-enumeration",
  "variables": [
    "av",
    "ba",
    "cu"
  ]
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Three-object assignment-by-elimination is a common puzzle shape; the pod/gem vocabulary and the specific constraint pattern are composed for this case, and no named benchmark is imitated.
AMBIGUITY_RISK: Low. 'Exactly one' and 'no two the same' are stated explicitly.
STRUCTURAL_UNIQUENESS_RATIONALE: The classic elimination structure with a forced last slot, instantiated with invented vocabulary and a single exclusion plus a single direct assignment — the family's unique-solution baseline.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Requires exact tracking of three disjoint slots; systems with weak assignment bookkeeping may fail access to the constraint capability through this representation.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Three-object assignment-by-elimination is a common puzzle shape; the pod/gem vocabulary and the specific constraint pattern are composed for this case, and no named benchmark is imitated.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-022
PROPOSED_REASONING_FAMILY: constraint-quantitative
STRUCTURAL_SIGNATURE: 3 pods over 2 values with bijection constraint plus two partial constraints, empty solution set
PREMISES:
1. Three pods — the eb, the fyn, and the got — each hold exactly one gem, and no two pods hold the same gem.
2. The only available gems are the sun and the moon.
3. The eb does not hold the moon.
4. The fyn holds the sun.
QUESTION: Do the four numbered conditions admit any valid assignment of gems to pods? Answer with: yes or no.
EXPECTED_PROPERTY: Recognition of structural impossibility (three pairwise-distinct values cannot be drawn from a two-value domain), reported as a definite negative.
INTENDED_CORRECT_ANSWER: No — no valid assignment exists.
DERIVATION:
1. By premise 2 there are exactly two gems; by premise 1 the three pods must hold pairwise different gems.
2. Three pairwise different values cannot be drawn from a set of two: after the sun and the moon are used, no third distinct gem remains for the third pod.
3. Premises 3 and 4 are individually satisfiable but do not remove the counting conflict.
4. No assignment satisfies all conditions; the answer is no.
GROUND_TRUTH_CLASS: IMPOSSIBLE
GROUND_TRUTH_STATEMENT: a valid assignment of gems to pods exists
FORBIDDEN_SHORTCUTS:
- Do not relax 'no two pods hold the same gem' to force a solution.
- Do not treat the constraints in isolation — the impossibility is joint.
FORMAL:
```json
{
  "domains": {
    "eb": [
      "sun",
      "moon"
    ],
    "fyn": [
      "sun",
      "moon"
    ],
    "got": [
      "sun",
      "moon"
    ]
  },
  "premises": [
    {
      "kind": "all_different",
      "vars": [
        "eb",
        "fyn",
        "got"
      ]
    },
    {
      "kind": "not_equal",
      "value": "moon",
      "var": "eb"
    },
    {
      "kind": "equals",
      "value": "sun",
      "var": "fyn"
    }
  ],
  "query": {
    "kind": "solution_exists"
  },
  "semantics": "constraint-enumeration",
  "variables": [
    "eb",
    "fyn",
    "got"
  ]
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Pigeonhole-style impossibility is a known puzzle family; the pod/gem dressing and the two partial constraints make this instance distinct from textbook phrasings.
AMBIGUITY_RISK: Low. The domain size and the distinctness requirement are both explicit.
STRUCTURAL_UNIQUENESS_RATIONALE: An impossibility case whose obstruction is cardinality (three into two) rather than a direct constraint clash, with two satisfiable partial constraints included so that local checking does not reveal the conflict.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Impossibility verdicts require exhaustive reasoning; a system that samples assignments rather than enumerating may misreport possibility — a representation-induced failure mode, disclosed.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Pigeonhole-style impossibility is a known puzzle family; the pod/gem dressing and the two partial constraints make this instance distinct from textbook phrasings.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-023
PROPOSED_REASONING_FAMILY: constraint-quantitative
STRUCTURAL_SIGNATURE: 3x3 bijection with a single exclusion only, slot query varying across two exhibited solutions
PREMISES:
1. Three pods — the heb, the ivy, and the jor — each hold exactly one gem, and no two pods hold the same gem.
2. The three available gems are the amm, the bly, and the cre.
3. The heb does not hold the amm.
QUESTION: Does the ivy hold the amm? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Recognition that the queried slot differs across valid assignments, with both assignments exhibited, producing a reported indeterminacy.
INTENDED_CORRECT_ANSWER: Cannot be determined — the ivy holds the amm in some valid assignments and not in others.
DERIVATION:
1. With premise 3, the amm must be held by the ivy or the jor.
2. Assignment A: heb = bly, ivy = amm, jor = cre — satisfies all premises, with the ivy holding the amm.
3. Assignment B: heb = cre, ivy = bly, jor = amm — satisfies all premises, with the ivy not holding the amm.
4. Since both assignments are valid, the queried statement is neither forced nor refuted; the answer is cannot be determined.
GROUND_TRUTH_CLASS: INDETERMINATE
GROUND_TRUTH_STATEMENT: the ivy holds the amm
FORBIDDEN_SHORTCUTS:
- Do not pick a favorite assignment; both exhibited assignments must be checked against all premises.
- Do not answer 'no' merely because the amm was excluded from the heb.
FORMAL:
```json
{
  "domains": {
    "heb": [
      "amm",
      "bly",
      "cre"
    ],
    "ivy": [
      "amm",
      "bly",
      "cre"
    ],
    "jor": [
      "amm",
      "bly",
      "cre"
    ]
  },
  "premises": [
    {
      "kind": "all_different",
      "vars": [
        "heb",
        "ivy",
        "jor"
      ]
    },
    {
      "kind": "not_equal",
      "value": "amm",
      "var": "heb"
    }
  ],
  "query": {
    "kind": "truth_of",
    "value": "amm",
    "var": "ivy"
  },
  "semantics": "constraint-enumeration",
  "variables": [
    "heb",
    "ivy",
    "jor"
  ]
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Under-constrained assignment probes are common; the invented gem vocabulary and the single-exclusion shape are composed for this case.
AMBIGUITY_RISK: Low. The question offers abstention and the two assignments are checkable.
STRUCTURAL_UNIQUENESS_RATIONALE: An abstention case whose indeterminacy arises from symmetric solution multiplicity, not from missing links: the same bijection structure that yields a unique answer in the elimination case yields a two-model indeterminacy here with one fewer constraint.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Requires comparing at least two complete assignments; systems that stop at the first satisfying assignment will misreport determinacy.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Under-constrained assignment probes are common; the invented gem vocabulary and the single-exclusion shape are composed for this case.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-024
PROPOSED_REASONING_FAMILY: constraint-quantitative
STRUCTURAL_SIGNATURE: 3-variable exact arithmetic chain (additive + multiplicative links), numeric value query
PREMISES:
1. The jal holds 5 beads.
2. The kiv holds 3 more beads than the jal.
3. The hox holds twice as many beads as the kiv.
QUESTION: How many beads does the hox hold? Answer with a number, or cannot be determined.
EXPECTED_PROPERTY: An exact three-step numeric derivation with a unique value, where partial misreadings produce different detectable integers.
INTENDED_CORRECT_ANSWER: 16 beads.
DERIVATION:
1. From premise 1: the jal holds 5 beads.
2. From premise 2: the kiv holds 5 + 3 = 8 beads.
3. From premise 3: the hox holds 2 × 8 = 16 beads.
4. Each premise fixes the next quantity exactly, so the value is unique.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the hox holds 16 beads
FORBIDDEN_SHORTCUTS:
- Do not approximate or round; the arithmetic is exact.
- Do not misread 'twice as many beads as the kiv' as 'twice as many beads as the jal'.
FORMAL:
```json
{
  "domains": {
    "hox": {
      "range": [
        0,
        20
      ]
    },
    "jal": {
      "range": [
        0,
        20
      ]
    },
    "kiv": {
      "range": [
        0,
        20
      ]
    }
  },
  "premises": [
    {
      "kind": "equals",
      "value": 5,
      "var": "jal"
    },
    {
      "expr": "kiv - jal = 3",
      "kind": "linear"
    },
    {
      "expr": "hox - 2 * kiv = 0",
      "kind": "linear"
    }
  ],
  "query": {
    "kind": "value_of",
    "var": "hox"
  },
  "semantics": "constraint-enumeration",
  "variables": [
    "jal",
    "kiv",
    "hox"
  ]
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Arithmetic word problems are ubiquitous; the invented container names and the specific 5/3/2 composition make verbatim retrieval unlikely while the numeric pattern remains simple.
AMBIGUITY_RISK: Low. The quantities are exact and the relations are standard comparatives.
STRUCTURAL_UNIQUENESS_RATIONALE: An exact-arithmetic chain whose links are heterogeneous (additive then multiplicative) and whose designed distractor value (doubling the wrong variable gives 10) makes the common error detectable in evaluation.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Arithmetic word problems are heavily represented in pretraining corpora; high performance here is compatible with pattern recall, and this is disclosed rather than treated as evidence of novel reasoning.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Arithmetic word problems are ubiquitous; the invented container names and the specific 5/3/2 composition make verbatim retrieval unlikely while the numeric pattern remains simple.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-025
PROPOSED_REASONING_FAMILY: constraint-quantitative
STRUCTURAL_SIGNATURE: two immediately-before blocks + slot exclusion over 4 slots, unique block orientation, slot query
PREMISES:
1. Four tasks — the wash, the etch, the seal, and the pack — occupy the four consecutive slots 1, 2, 3, and 4, one task per slot.
2. The wash runs immediately before the etch.
3. The seal runs immediately before the pack.
4. The seal does not run in slot 1.
QUESTION: In which slot does the seal run? Answer with a slot number, or cannot be determined.
EXPECTED_PROPERTY: A block-pair argument: two adjacent pairs must occupy slots 1–2 and 3–4, and the slot exclusion forces the orientation, yielding a unique schedule.
INTENDED_CORRECT_ANSWER: Slot 3.
DERIVATION:
1. By premises 2 and 3, the four tasks form two adjacent pairs: (wash, etch) and (seal, pack).
2. Two adjacent pairs must occupy slots 1–2 and 3–4 in some order.
3. If (seal, pack) occupied slots 1–2, the seal would run in slot 1, contradicting premise 4.
4. Hence (wash, etch) take slots 1–2 and (seal, pack) take slots 3–4: the seal runs in slot 3, and the full schedule is unique (wash = 1, etch = 2, seal = 3, pack = 4).
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the seal runs in slot 3
FORBIDDEN_SHORTCUTS:
- Do not treat 'immediately before' as merely 'before'.
- Do not fix the wash in slot 1 by naming order; only the block argument forces it.
FORMAL:
```json
{
  "domains": {
    "etch": {
      "range": [
        1,
        4
      ]
    },
    "pack": {
      "range": [
        1,
        4
      ]
    },
    "seal": {
      "range": [
        1,
        4
      ]
    },
    "wash": {
      "range": [
        1,
        4
      ]
    }
  },
  "premises": [
    {
      "kind": "all_different",
      "vars": [
        "wash",
        "etch",
        "seal",
        "pack"
      ]
    },
    {
      "a": "wash",
      "b": "etch",
      "kind": "immediately_before"
    },
    {
      "a": "seal",
      "b": "pack",
      "kind": "immediately_before"
    },
    {
      "kind": "not_equal",
      "value": 1,
      "var": "seal"
    }
  ],
  "query": {
    "kind": "value_of",
    "var": "seal"
  },
  "semantics": "constraint-enumeration",
  "variables": [
    "wash",
    "etch",
    "seal",
    "pack"
  ]
}
```
DIFFICULTY: DEEP
RETRIEVAL_RISK: Block-scheduling puzzles are common in aptitude tests; the specific two-block-plus-exclusion composition and task names are arranged for this case so that the orientation step is forced rather than guessed.
AMBIGUITY_RISK: Low. 'Immediately before' and the slot exclusion are explicit.
STRUCTURAL_UNIQUENESS_RATIONALE: A two-block scheduling case whose uniqueness comes from block orientation rather than slot-by-slot elimination; the reasoning level (partition into adjacent pairs, then orient) sits above single-adjacency checks.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Requires composing two adjacency facts into a partition argument; systems that check constraints one at a time will not find the forcing structure through this representation.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Block-scheduling puzzles are common in aptitude tests; the specific two-block-plus-exclusion composition and task names are arranged for this case so that the orientation step is forced rather than guessed.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-026
PROPOSED_REASONING_FAMILY: default-exception
STRUCTURAL_SIGNATURE: single default with two named exceptions explicitly absent, applicability query derivable
PREMISES:
1. Normally, if a creature is a wob, then it can fly, unless it is a fen or a mup.
2. The tav is a wob.
3. It is established that the tav is neither a fen nor a mup.
QUESTION: Can the tav fly? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Application of a normal-case rule when its applicability condition is recorded (exceptions explicitly absent), yielding the default conclusion.
INTENDED_CORRECT_ANSWER: Yes — the tav can fly (by the normal-case rule; neither exception is established).
DERIVATION:
1. Premise 2 satisfies the condition of the normal-case rule in premise 1.
2. Premise 3 establishes that neither exception (fen, mup) applies to the tav.
3. With the rule's condition met and no exception in force, the normal conclusion holds: the tav can fly.
4. The answer is yes.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the tav can fly
FORBIDDEN_SHORTCUTS:
- Do not answer 'cannot be determined' merely because exceptions exist in the rule; premise 3 records that they do not apply here.
- Do not import real-world bird facts; the wob/fen/mup vocabulary is self-contained.
FORMAL:
```json
{
  "premises": [
    {
      "kind": "prop_fact",
      "prop": "wob_tav",
      "value": true
    },
    {
      "kind": "prop_fact",
      "prop": "fen_tav",
      "value": false
    },
    {
      "kind": "prop_fact",
      "prop": "mup_tav",
      "value": false
    },
    {
      "if": [
        {
          "prop": "wob_tav",
          "value": true
        }
      ],
      "kind": "default",
      "normally": {
        "prop": "flies_tav",
        "value": true
      },
      "unless": [
        {
          "prop": "fen_tav",
          "value": true
        },
        {
          "prop": "mup_tav",
          "value": true
        }
      ]
    }
  ],
  "props": [
    "wob_tav",
    "flies_tav",
    "fen_tav",
    "mup_tav"
  ],
  "query": {
    "prop": "flies_tav",
    "value": true
  },
  "semantics": "default-extensions"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Default-rule probes with explicit exceptions are less common than plain conditionals; the invented wob/fen/mup vocabulary composes a self-contained instance.
AMBIGUITY_RISK: Low. 'Normally ... unless' is the only non truth-functional construction, and its applicability is recorded by premise 3.
STRUCTURAL_UNIQUENESS_RATIONALE: The single-default applicability case: the exceptions are explicitly recorded as absent, so the default fires without precedence reasoning — the family's baseline for rule application.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: 'Normally ... unless' must be read as a default, not a strict conditional or a biconditional; misreading the modality changes the verdict without indicating a reasoning defect.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Default-rule probes with explicit exceptions are less common than plain conditionals; the invented wob/fen/mup vocabulary composes a self-contained instance.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-027
PROPOSED_REASONING_FAMILY: default-exception
STRUCTURAL_SIGNATURE: exception fact present + explicit no-other-rule statement, blocked default yields indeterminacy
PREMISES:
1. Normally, if a vehicle is a kar, then it is blue, unless it is a dul.
2. The zip is a kar.
3. The zip is a dul.
4. No rule in this set states what color a dul has.
QUESTION: Is the zip blue? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Recognition that an established exception blocks the default without implying the negation of its conclusion, and that nothing else fixes the queried property.
INTENDED_CORRECT_ANSWER: Cannot be determined — the exception blocks the normal rule, and nothing else fixes the color.
DERIVATION:
1. Premise 3 establishes the exception of premise 1, so the normal-case rule does not apply to the zip.
2. A blocked default does not imply the negation of its conclusion; premise 4 records that no other rule fixes the color of a dul.
3. Neither 'the zip is blue' nor its negation is derivable.
4. The answer is cannot be determined.
GROUND_TRUTH_CLASS: INDETERMINATE
GROUND_TRUTH_STATEMENT: the zip is blue
FORBIDDEN_SHORTCUTS:
- Do not treat the blocked default as implying that the zip is not blue.
- Do not import real-world expectations about vehicle colors.
FORMAL:
```json
{
  "premises": [
    {
      "kind": "prop_fact",
      "prop": "kar_zip",
      "value": true
    },
    {
      "kind": "prop_fact",
      "prop": "dul_zip",
      "value": true
    },
    {
      "if": [
        {
          "prop": "kar_zip",
          "value": true
        }
      ],
      "kind": "default",
      "normally": {
        "prop": "blue_zip",
        "value": true
      },
      "unless": [
        {
          "prop": "dul_zip",
          "value": true
        }
      ]
    }
  ],
  "props": [
    "kar_zip",
    "blue_zip",
    "dul_zip"
  ],
  "query": {
    "prop": "blue_zip",
    "value": true
  },
  "semantics": "default-extensions"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Exception-blocking probes are a known default-logic shape; the invented kar/dul/zip vocabulary and the explicit no-other-rule statement keep the instance self-contained.
AMBIGUITY_RISK: Low. The blocking fact is direct and the absence of other rules is recorded.
STRUCTURAL_UNIQUENESS_RATIONALE: The exception-blocking case: the abstention arises from rule inapplicability (a blocked default), which is a different mechanism from missing premises or symmetric solution multiplicity.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: The 'blocked default is not a negation' convention is stated in the premises; a system that maps 'unless' to 'implies not' will misread the modality — representational, not reasoning.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Exception-blocking probes are a known default-logic shape; the invented kar/dul/zip vocabulary and the explicit no-other-rule statement keep the instance self-contained.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-028
PROPOSED_REASONING_FAMILY: default-exception
STRUCTURAL_SIGNATURE: applicable default + contrary explicit fact + stated precedence rule, fact-overrides-default refutation
PREMISES:
1. Normally, if a stone is a vel, then it sinks in water, unless it is a pyx.
2. The om is a vel.
3. The om is not a pyx.
4. The om does not sink in water.
5. Where an explicit statement conflicts with what a normal-case rule would conclude, the explicit statement wins.
QUESTION: Does the om sink in water? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Resolution of a default-versus-fact conflict through the stated precedence rule, ending in a definite refutation rather than an inconsistency report.
INTENDED_CORRECT_ANSWER: No — the om does not sink in water (the explicit fact overrides the normal-case conclusion).
DERIVATION:
1. Premises 2 and 3 make the normal-case rule of premise 1 applicable to the om, so it would conclude that the om sinks.
2. Premise 4 explicitly states the opposite.
3. By the precedence rule in premise 5, the explicit statement prevails over the normal-case conclusion.
4. The om does not sink; the queried statement is refuted and the answer is no.
GROUND_TRUTH_CLASS: CONTRADICTED
GROUND_TRUTH_STATEMENT: the om sinks in water
FORBIDDEN_SHORTCUTS:
- Do not declare the premises inconsistent and stop; the precedence rule (premise 5) resolves the conflict deterministically.
- Do not let the default override the explicit fact — the direction of precedence is stated.
FORMAL:
```json
{
  "premises": [
    {
      "kind": "prop_fact",
      "prop": "vel_om",
      "value": true
    },
    {
      "kind": "prop_fact",
      "prop": "pyx_om",
      "value": false
    },
    {
      "kind": "prop_fact",
      "prop": "sinks_om",
      "value": false
    },
    {
      "if": [
        {
          "prop": "vel_om",
          "value": true
        }
      ],
      "kind": "default",
      "normally": {
        "prop": "sinks_om",
        "value": true
      },
      "unless": [
        {
          "prop": "pyx_om",
          "value": true
        }
      ]
    }
  ],
  "props": [
    "vel_om",
    "pyx_om",
    "sinks_om"
  ],
  "query": {
    "prop": "sinks_om",
    "value": true
  },
  "semantics": "default-extensions"
}
```
DIFFICULTY: MEDIUM
RETRIEVAL_RISK: Precedence-rule probes are uncommon in public corpora; the invented vel/pyx/om vocabulary and the explicit priority statement compose a self-contained instance.
AMBIGUITY_RISK: Low. The precedence direction is stated as a premise.
STRUCTURAL_UNIQUENESS_RATIONALE: The precedence case: a fact and an applicable default collide and a stated priority rule resolves it — testing rule-priority handling rather than mere default application or blocking.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Requires distinguishing modal force (explicit fact vs normal-case conclusion); systems that flatten modalities will either report inconsistency or follow the default — both misread the representation.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Precedence-rule probes are uncommon in public corpora; the invented vel/pyx/om vocabulary and the explicit priority statement compose a self-contained instance.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-029
PROPOSED_REASONING_FAMILY: default-exception
STRUCTURAL_SIGNATURE: twin applicable defaults with opposite conclusions and no precedence, designed two-extension ambiguity
PREMISES:
1. Normally, if a bird is a gwil, then it sings at dawn, unless it is unwell.
2. Normally, if a bird is a hed, then it is silent at dawn, unless it is unwell.
3. The nor is a gwil and a hed.
4. The nor is not unwell.
QUESTION: Does the nor sing at dawn? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Recognition of designed ambiguity: both normal-case rules are applicable and conclude opposites, no precedence is given, and the indeterminacy is reported with the ambiguity made explicit.
INTENDED_CORRECT_ANSWER: Cannot be determined — the two normal-case rules conflict for the nor and no precedence between them is stated; both conclusions are defensible and the ambiguity is inherent in the rules.
DERIVATION:
1. Premises 3 and 4 make both normal-case rules applicable (neither exception holds).
2. Applying premise 1's rule yields: the nor sings at dawn. Applying premise 2's rule yields: the nor is silent at dawn.
3. Each application set is internally consistent, but jointly they conflict, and no premise states a priority between the two rules.
4. Two defensible extensions exist and they disagree on the query; the answer is cannot be determined, and the ambiguity is reported rather than resolved.
GROUND_TRUTH_CLASS: INDETERMINATE
GROUND_TRUTH_STATEMENT: the nor sings at dawn
GROUND_TRUTH_AMBIGUITY_NOTE: conflicting-defaults-two-extensions: the indeterminacy is by design (twin applicable defaults, no precedence); per order §6 the ambiguity is reported, not forced into a determinate answer.
FORBIDDEN_SHORTCUTS:
- Do not silently prefer the first-stated rule (premise 1) over the second.
- Do not report the premises as inconsistent — they are consistent; it is the rule applications that conflict, and the correct response is to report the indeterminacy.
FORMAL:
```json
{
  "premises": [
    {
      "kind": "prop_fact",
      "prop": "gwil_nor",
      "value": true
    },
    {
      "kind": "prop_fact",
      "prop": "hed_nor",
      "value": true
    },
    {
      "kind": "prop_fact",
      "prop": "unwell_nor",
      "value": false
    },
    {
      "if": [
        {
          "prop": "gwil_nor",
          "value": true
        }
      ],
      "kind": "default",
      "normally": {
        "prop": "sings_nor",
        "value": true
      },
      "unless": [
        {
          "prop": "unwell_nor",
          "value": true
        }
      ]
    },
    {
      "if": [
        {
          "prop": "hed_nor",
          "value": true
        }
      ],
      "kind": "default",
      "normally": {
        "prop": "sings_nor",
        "value": false
      },
      "unless": [
        {
          "prop": "unwell_nor",
          "value": true
        }
      ]
    }
  ],
  "props": [
    "gwil_nor",
    "hed_nor",
    "unwell_nor",
    "sings_nor"
  ],
  "query": {
    "prop": "sings_nor",
    "value": true
  },
  "semantics": "default-extensions"
}
```
DIFFICULTY: DEEP
RETRIEVAL_RISK: Conflicting-defaults probes (twin rules, no precedence) are rare relative to single-default cases; the invented gwil/hed/nor vocabulary composes a self-contained instance.
AMBIGUITY_RISK: Moderate by design: the ambiguity is the phenomenon under test and is recorded in the ground truth itself, per the protocol's ambiguity-reporting rule.
STRUCTURAL_UNIQUENESS_RATIONALE: The designed-ambiguity case: two applicable defaults with opposite conclusions and no precedence; the ground truth records a genuine two-extension indeterminacy — the calibrated-abstention target of the family.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: The abstention option is offered without any signal that it is correct; systems biased toward decisive answers will resolve the conflict arbitrarily — a representational pressure that the case deliberately measures.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Conflicting-defaults probes (twin rules, no precedence) are rare relative to single-default cases; the invented gwil/hed/nor vocabulary composes a self-contained instance.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

CASE ID: N-030
PROPOSED_REASONING_FAMILY: default-exception
STRUCTURAL_SIGNATURE: two-link default chain (second rule's condition is a default conclusion), terminal query derivable
PREMISES:
1. Normally, if a plant is a ser, then it blooms, unless it is kept in the dark.
2. Normally, if a plant blooms, then it is fragrant, unless it is diseased.
3. The pyr is a ser.
4. The pyr is not kept in the dark.
5. Nothing states or implies that the pyr is diseased.
QUESTION: Is the pyr fragrant? Answer with: yes, no, or cannot be determined.
EXPECTED_PROPERTY: Iterated default reasoning: the second rule's condition is itself the first rule's conclusion, with both exceptions controlled, ending in a definite terminal conclusion.
INTENDED_CORRECT_ANSWER: Yes — the pyr is fragrant (the first normal-case rule yields blooming; the second then yields fragrance).
DERIVATION:
1. Premises 3 and 4 make premise 1's rule applicable: the pyr blooms.
2. Premise 5 records that the disease exception is not established; with blooming derived, premise 2's rule applies: the pyr is fragrant.
3. The answer is yes.
GROUND_TRUTH_CLASS: DERIVABLE
GROUND_TRUTH_STATEMENT: the pyr is fragrant
FORBIDDEN_SHORTCUTS:
- Do not require the exceptions to be affirmatively disproven beyond what premises 4 and 5 record.
- Do not stop at 'blooms' — the query is about the second link.
FORMAL:
```json
{
  "premises": [
    {
      "kind": "prop_fact",
      "prop": "ser_pyr",
      "value": true
    },
    {
      "kind": "prop_fact",
      "prop": "dark_pyr",
      "value": false
    },
    {
      "if": [
        {
          "prop": "ser_pyr",
          "value": true
        }
      ],
      "kind": "default",
      "normally": {
        "prop": "blooms_pyr",
        "value": true
      },
      "unless": [
        {
          "prop": "dark_pyr",
          "value": true
        }
      ]
    },
    {
      "if": [
        {
          "prop": "blooms_pyr",
          "value": true
        }
      ],
      "kind": "default",
      "normally": {
        "prop": "fragrant_pyr",
        "value": true
      },
      "unless": [
        {
          "prop": "diseased_pyr",
          "value": true
        }
      ]
    }
  ],
  "props": [
    "ser_pyr",
    "dark_pyr",
    "blooms_pyr",
    "diseased_pyr",
    "fragrant_pyr"
  ],
  "query": {
    "prop": "fragrant_pyr",
    "value": true
  },
  "semantics": "default-extensions"
}
```
DIFFICULTY: DEEP
RETRIEVAL_RISK: Chained default probes are uncommon; the invented ser/pyr vocabulary and the two-link structure with controlled exceptions compose a self-contained instance.
AMBIGUITY_RISK: Low. Both exceptions are handled by explicit premises.
STRUCTURAL_UNIQUENESS_RATIONALE: The chained-default case: the second rule's condition is itself a default conclusion, so iterated normal-case reasoning is required — one level above single-default application and without any conflict.
REPRESENTATION_BIAS_DISCLOSURE:
STATUS: DISCLOSED
EVIDENCE: Natural-language premises and question only; the formal layer is protected qualification material.
KNOWN_LIMITATION: Two-step default chains require carrying a derived modal conclusion into a further rule's condition; representational loss at the intermediate link ('blooms') breaks the chain invisibly.
ENVIRONMENTAL_PRE_CHECK:
KNOWLEDGE_SOURCES: Chained default probes are uncommon; the invented ser/pyr vocabulary and the two-link structure with controlled exceptions compose a self-contained instance.
FIXTURES: NONE
IMPLEMENTATION_ARTIFACTS: NONE
MEMORY_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
MODEL_ACCESS_PATHS: NOT-APPLICABLE (no execution has occurred at authoring)
ANSWER_BEARING_ARTIFACTS: ground truth, derivation and formal layer stored in the private qualification area; excluded from any public case view
SELF_REVIEW:
- Derivable: Yes
- Unique: Yes
- Self-contained: Yes
- No external knowledge: Yes
- No real-world entity dependency: Yes
- Structurally distinct: Yes
---

AUTHORING PROVENANCE
author identity: ECP session executor agent (GLM-family LLM) operating under owner order M3-CA0 v1 — authoring executor, NOT an external independent author
authoring environment: executor session host; Python 3.12 toolchain for deterministic assembly; no network access used for authoring; no evaluated system accessed during authoring
model/tool: GLM-family conversational agent (this session) authoring content directly; deterministic Python scripts for document assembly
model/version: NOT AVAILABLE (session model build identifier not exposed)
prompt/instructions: owner order M3-CA0 v1, sections 0-17 (sha256 2695594b70b238959b5c7ffa9180c8adb16b6a66588fdfa0eb53685d900459fd)
information available: complete ECP repository at commit 5f12ee3 (spec, schemas, modules, docs including the three frozen G0 design documents); prior case review areas R1 and R2 (qualification-stage records of the 20-candidate pilot: reviews, adjudications, amendments); M3-CA0-B decision record ECP-OWNDEC-000001; prior candidate case-set content
information explicitly unavailable: any evaluated-system performance data (none exists project-wide — zero registered cases, zero executions, zero results); any model outputs on these new cases (no model was invoked on them); sealed ground truth of hidden evaluation cases (no hidden set exists, no set-class designation performed); future execution outcomes (postdate authoring by construction)
relationship to ECP developers: the author IS the ECP project's executor agent (developer-side party) — personal and organizational independence NOT established
relationship to evaluated systems: none during authoring — no evaluated system was queried or accessed; the JARVIS repository exists on the host but was not opened during this phase; cases contain no system-specific identifiers
access to prior ECP results: qualification-stage results of the prior 20-candidate pool — YES (reviews/adjudications/amendments consulted for failure modes); execution/outcome results — NO ACCESS (none exist anywhere in the project)
independence status: NOT-INDEPENDENT — EXECUTOR-AUTHORED, PERFORMANCE-BLIND, SYSTEM-NEUTRAL. Case-author independence: NOT-INDEPENDENT (executor is the ECP-side party; model-family overlap with the prior population author glm-4-plus — same GLM family, carried fact ECP-ADJ-000003). Performance blindness: YES-BY-CONSTRUCTION (no outcome data exists at authoring; no model consulted). System neutrality: YES-DECLARED (no evaluated-system access; no implementation-specific identifiers). Per order §3 the author is NOT described as independent merely because a different model or tool was used; this block is the explicit record.
independence limitations (declared): model-family overlap with the prior population author; executor-authored (developer-side party); author had repository access including review-layer internals (disclosed, not spec-face-only); natural-language-to-formal correspondence is author-attested, not mechanically verified (partial mechanical coverage checks are applied by the qualification engine)
validation procedure: authoring-time structural self-checks + deterministic qualification engine verification (order §15) at intake; no model was executed at any point
authored_at: 2026-09-09T03:55:45Z

CASE SET SUMMARY
candidate_count: 30
reasoning_family_distribution: conditional-chaining = 5; consistency-contradiction = 5; constraint-quantitative = 5; default-exception = 5; relational-discrimination = 5; transitive-relational = 5
pool design: 6 reasoning families (5 candidates each). Pool is deliberately larger than any plausibly eventual registered evaluation set (order §4). No case was selected, tuned, or filtered on expected difficulty or expected system performance — no performance data exists (zero executions project-wide); difficulty diversity is a design axis recorded per case, never a performance-driven selection
ground_truth_class_distribution: CONTRADICTED = 8; DERIVABLE = 14; IMPOSSIBLE = 1; INDETERMINATE = 7 — designed indeterminacy cases (calibrated abstention) are marked and their ambiguity reported per order §6, never forced into a determinate class
difficulty_distribution: DEEP = 5; MEDIUM = 19; SHALLOW = 6
uniform answer formats: every question states the same allowed answer options regardless of the true class (no answer-format leakage of the ground truth)
rotation preservation (order §12): no set-class designation is performed at authoring — all 30 candidates are unassigned pool material; partition into public development / preregistered / hidden / rotating / private sets is deferred to the Registration gate under owner authorization; no hidden material is created or exposed; qualification is performance-blind, so the eventual registered population cannot be defined as whatever survived after seeing model performance
registration boundary (order §14): no ECP-CASE ids are assigned; no registration records; no execution status; no frozen evaluation set; the public ledger remains at genesis
execution boundary (order §13): no evaluated model was invoked at any point during authoring or assembly; ground truth was established and mechanically verified without consulting any evaluated system
