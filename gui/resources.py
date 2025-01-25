VIS_JS_CONTENT = """
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/vis-network.min.js"></script>
"""

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>网络拓扑图</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #ffffff;
        }
        #topology {
            width: 100vw;
            height: 100vh;
            position: absolute;
            top: 0;
            left: 0;
            background-image: 
                linear-gradient(#e5e5e5 1px, transparent 1px),
                linear-gradient(90deg, #e5e5e5 1px, transparent 1px);
            background-size: 20px 20px;
        }
    </style>
</head>
<body>
    <div id="topology"></div>
    <script>
        var data = {plotly_data};
        
        var layout = {
            showlegend: false,
            hovermode: 'closest',
            dragmode: 'select',
            clickmode: 'event+select',
            margin: {
                l: 50,
                r: 50,
                b: 50,
                t: 50,
                pad: 10
            },
            xaxis: {
                showgrid: true,
                zeroline: false,
                showticklabels: false,
                showspikes: true,
                gridcolor: '#e5e5e5',
                gridwidth: 1,
                range: [-2, 2]
            },
            yaxis: {
                showgrid: true,
                zeroline: false,
                showticklabels: false,
                showspikes: true,
                gridcolor: '#e5e5e5',
                gridwidth: 1,
                range: [-2, 2]
            },
            plot_bgcolor: '#ffffff',
            paper_bgcolor: '#ffffff'
        };
        
        var config = {
            displayModeBar: true,
            responsive: true,
            scrollZoom: true,
            editable: true,
            modeBarButtonsToAdd: [
                'hoverClosestGl2d',
                'toggleSpikelines',
                'resetScale2d'
            ],
            displaylogo: false
        };
        
        var myPlot = document.getElementById('topology');
        var isNodeDragging = false;
        var selectedNodeIndex = -1;
        
        Plotly.newPlot(myPlot, data, layout, config).then(function() {
            // 初始化节点连接关系
            var edgeTrace = data[0];
            var nodeTrace = data[1];
            
            // 创建节点到边的映射
            var nodeEdges = {};
            for (var i = 0; i < nodeTrace.x.length; i++) {
                nodeEdges[i] = {
                    sourceEdges: [],  // 作为源节点的边
                    targetEdges: []   // 作为目标节点的边
                };
            }
            
            // 遍历所有边，建立映射关系
            for (var i = 0; i < edgeTrace.x.length; i += 3) {
                var sourceNode = Math.floor(i/3);
                var targetNode = (sourceNode + 1) % nodeTrace.x.length;  // 使用取模确保不越界
                
                // 记录边的索引
                nodeEdges[sourceNode].sourceEdges.push(i);      // 起点
                nodeEdges[targetNode].targetEdges.push(i + 1);  // 终点
            }
            
            myPlot.on('plotly_click', function(eventData) {
                var pts = eventData.points[0];
                if (pts.curveNumber === 1) {  // 点击的是节点
                    isNodeDragging = true;
                    selectedNodeIndex = pts.pointIndex;
                }
            });
            
            myPlot.addEventListener('mousemove', function(evt) {
                if (isNodeDragging && selectedNodeIndex !== -1) {
                    var rect = myPlot.getBoundingClientRect();
                    var xaxis = myPlot._fullLayout.xaxis;
                    var yaxis = myPlot._fullLayout.yaxis;
                    
                    // 计算新位置
                    var newX = xaxis.p2c(evt.clientX - rect.left);
                    var newY = yaxis.p2c(evt.clientY - rect.top);
                    
                    // 更新节点位置
                    var nodeTrace = data[1];
                    nodeTrace.x[selectedNodeIndex] = newX;
                    nodeTrace.y[selectedNodeIndex] = newY;
                    
                    // 更新连接线
                    var edgeTrace = data[0];
                    
                    // 更新该节点作为源节点的边
                    nodeEdges[selectedNodeIndex].sourceEdges.forEach(function(edgeIndex) {
                        edgeTrace.x[edgeIndex] = newX;
                        edgeTrace.y[edgeIndex] = newY;
                    });
                    
                    // 更新该节点作为目标节点的边
                    nodeEdges[selectedNodeIndex].targetEdges.forEach(function(edgeIndex) {
                        edgeTrace.x[edgeIndex] = newX;
                        edgeTrace.y[edgeIndex] = newY;
                    });
                    
                    Plotly.redraw(myPlot);
                }
            });
            
            document.addEventListener('mouseup', function() {
                isNodeDragging = false;
                selectedNodeIndex = -1;
            });
            
            window.addEventListener('resize', function() {
                Plotly.Plots.resize(myPlot);
            });
        });
    </script>
</body>
</html>
'''