MATCH 
(e1:Event)-[*]->(e2:Event)-[*]->(e3:Event),
 (e1)-[]->(f1:Fact),
 (e2)-[]->(f2:Fact),
 (e3)-[]->(f3:Fact)
WHERE
 [f1.class, f1.octave] IN [['d', 4], ['e', 4], ['f', 4], ['g', 4]] AND f1.dur <= 8 AND f1.dur >= 3 AND
 [f2.class, f2.octave] IN [['g', 4], ['a', 4], ['b', 4], ['c', 5]] AND f2.dur <= 8 AND f2.dur >= 3 AND
 [f3.class, f3.octave] IN [['d', 5], ['e', 5], ['f', 5], ['g', 5]] AND f3.dur <= 8 AND f3.dur >= 3 AND 
 e1.end >= e2.start - 0.1 AND e2.end >= e3.start - 0.1
RETURN e1.id, e2.id, e3.id

MATCH 
(e1:Event)-[*]->(e2:Event)-[*]->(e3:Event),
(e1)-[]->(f1:Fact),
(e2)-[]->(f2:Fact),
(e3)-[]->(f3:Fact)
WHERE
f1.frequency >= 880.0 AND f1.frequency <= 1244.51 AND e1.duration >= 0.125 AND e1.duration <= 0.375 AND
f2.frequency >= 369.99 AND f2.frequency <= 523.25 AND e2.duration >= 0.125 AND e2.duration <= 0.375 AND
f3.frequency >= 880.0 AND f3.frequency <= 1244.51 AND e3.duration >= 0.125 AND e3.duration <= 0.375 AND 
e1.end >= e2.start - 0.5 AND e2.end >= e3.start - 0.5
RETURN f1.class AS pitch_1, f1.octave AS octave_1, e1.duration AS duration_1, e1.start AS start_1, e1.end AS end_1, 
    f2.class AS pitch_2, f2.octave AS octave_2, e2.duration AS duration_2, e2.start AS start_2, e2.end AS end_2, 
    f3.class AS pitch_3, f3.octave AS octave_3, e3.duration AS duration_3, e3.start AS start_3, e3.end AS end_3