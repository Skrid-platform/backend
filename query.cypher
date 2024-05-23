MATCH
 TOLERANT pitch=1, duration=0.125, gap=0.25
 ALPHA 0.4
 (e1:Event)-[:NEXT]->(e2:Event)-[:NEXT]->(e3:Event)-[:NEXT]->(e4:Event)-[:NEXT]->(e5:Event)-[:NEXT]->(e6:Event)-[:NEXT]->(e7:Event)-[:NEXT]->(e8:Event)-[:NEXT]->(e9:Event)-[:NEXT]->(e10:Event),
 (e1)--(f1{class:'c',octave:5, dur:8.0}),
 (e2)--(f2{class:'d',octave:5, dur:8.0}),
 (e3)--(f3{class:'e',octave:5, dur:8.0}),
 (e4)--(f4{class:'e',octave:5, dur:8.0}),
 (e5)--(f5{class:'d',octave:5, dur:8.0}),
 (e6)--(f6{class:'c',octave:5, dur:8.0}),
 (e7)--(f7{class:'d',octave:5, dur:4.0}),
 (e8)--(f8{class:'c',octave:5, dur:8.0}),
 (e9)--(f9{class:'d',octave:5, dur:8.0}),
 (e10)--(f10{class:'e',octave:5, dur:8.0})
RETURN e1.source AS source, e1.start AS start