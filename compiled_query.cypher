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
 f1.frequency >= 1108.73 AND f1.frequency <= 1567.98 AND f1.duration >= 0.125 AND f1.duration <= 0.375 AND
 f2.frequency >= 369.99 AND f2.frequency <= 523.25 AND f2.duration >= 0.125 AND f2.duration <= 0.375 AND
 f3.frequency >= 2217.46 AND f3.frequency <= 3135.96 AND f3.duration >= 0.125 AND f3.duration <= 0.375
 e1.end >= e2.start - 0.25 AND e2.end >= e3.start - 0.25
RETURN e1.id, e2.id, e3.id