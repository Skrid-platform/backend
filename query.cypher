MATCH
 TOLERANT pitch=3, duration=0.125, gap=0.125
 ALPHA 0.4
 (e1:Event)-[:NEXT]->(e2:Event)-[:NEXT]->(e3:Event), 
 (e1)--(f1{class:'e',octave:4, dur:4}),
 (e2)--(f2{class:'a',octave:4, dur:4}),
 (e3)--(f3{class:'e',octave:5, dur:4})
RETURN e1.id, e2.id, e3.id