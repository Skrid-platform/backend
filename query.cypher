MATCH
 ALLOW_TRANSPOSITION
 TOLERANT pitch=3, duration=0.0, gap=0.0
 ALPHA 0.5
 (e1:Event)-[:NEXT]->(e2:Event)-[:NEXT]->(e3:Event)-[:NEXT]->(e4:Event)-[:NEXT]->(e5:Event)-[:NEXT]->(e6:Event)-[:NEXT]->(e7:Event),
 (e1)--(f1{class:'e',octave:5, dur:8}),
 (e2)--(f2{class:'e',octave:5, dur:4}),
 (e3)--(f3{class:'d',octave:5, dur:8}),
 (e4)--(f4{class:'c',octave:5, dur:8}),
 (e5)--(f5{class:'d',octave:5, dur:8}),
 (e6)--(f6{class:'e',octave:5, dur:8}),
 (e7)--(f7{class:'f',octave:5, dur:8})
RETURN e1.source AS source, e1.start AS start
