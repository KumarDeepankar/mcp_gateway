// agentic_assistant/static/js/chart_renderer.js
window.ChartRenderer = {
    renderChart: function(chartSpec, containerElement) {
        if (!chartSpec || !containerElement) {
            console.error("ChartSpec or container element missing for rendering.");
            containerElement.innerHTML = '<p style="color: red;">Error: Chart data or container missing.</p>';
            return;
        }

        // Clear previous chart content
        d3.select(containerElement).selectAll("*").remove();

        // Create header
        const header = d3.select(containerElement)
            .append('div')
            .attr('class', 'chart-header');

        const titleText = (chartSpec.options && chartSpec.options.title) ? 
                          chartSpec.options.title :
                          `${chartSpec.chart_type || 'Unknown'} Chart`;
        header.append('h4')
            .attr('class', 'chart-title')
            .text(titleText);

        if (typeof d3 === 'undefined') {
            console.error("D3.js library is not loaded.");
            const errorMsg = document.createElement('p');
            errorMsg.textContent = "D3.js library not loaded. Cannot render chart visually.";
            errorMsg.style.color = "red";
            containerElement.appendChild(errorMsg);
            return;
        }

        // Ensure global tooltip exists
        if (d3.select(".chart-tooltip").empty()) {
            d3.select("body").append("div")
                .attr("class", "chart-tooltip")
                .style("position", "absolute")
                .style("background", "white")
                .style("border", "1px solid #ccc")
                .style("border-radius", "4px")
                .style("padding", "8px")
                .style("font-size", "12px")
                .style("pointer-events", "none")
                .style("opacity", 0)
                .style("z-index", "1000")
                .style("box-shadow", "0 2px 4px rgba(0,0,0,0.1)");
        }

        try {
            this.renderChartByType(chartSpec, containerElement);
        } catch (error) {
            console.error("Error rendering chart:", error);
            containerElement.innerHTML += `<p style="color: red;">Error rendering chart: ${error.message}</p>`;
        }
    },

    renderChartByType: function(chartSpec, containerElement) {
        const container = d3.select(containerElement);
        
        if (!chartSpec || !chartSpec.chart_type || !chartSpec.data || !chartSpec.options) {
            container.append("p").attr("class", "error-message").text("Invalid chart specification received.");
            return;
        }

        // Calculate container dimensions
        const style = getComputedStyle(containerElement);
        const paddingX = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
        const buffer = 20;
        
        const svgWidth = Math.max(containerElement.clientWidth - paddingX - buffer, 400);
        const svgHeight = 400;

        // Create SVG
        const svg = container.append("svg")
            .attr("width", svgWidth)
            .attr("height", svgHeight)
            .style("overflow", "visible");

        const margin = {top: 30, right: 40, bottom: 100, left: 80};
        const chartWidth = svgWidth - margin.left - margin.right;
        const chartHeight = svgHeight - margin.top - margin.bottom;

        const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);
        const tooltip = d3.select(".chart-tooltip");

        try {
            switch (chartSpec.chart_type) {
                case "bar":
                    this.renderBarChart(g, chartSpec.data, chartSpec.options, chartWidth, chartHeight, tooltip);
                    break;
                case "line":
                    this.renderLineChart(g, chartSpec.data, chartSpec.options, chartWidth, chartHeight, tooltip);
                    break;
                case "scatter":
                    this.renderScatterPlot(g, chartSpec.data, chartSpec.options, chartWidth, chartHeight, tooltip);
                    break;
                case "pie":
                    this.renderPieChart(g, chartSpec.data, chartSpec.options, chartWidth, chartHeight, tooltip);
                    break;
                default:
                    container.append("p")
                        .attr("class", "error-message")
                        .text(`Unsupported chart type: ${chartSpec.chart_type}`);
            }
        } catch (renderError) {
            container.append("p")
                .attr("class", "error-message")
                .text(`D3 Render Error: ${renderError.message}`);
        }
    },

    renderBarChart: function(g, data, options, width, height, tooltip) {
        const xField = options.x_field || Object.keys(data[0])[0];
        const yField = options.y_field || Object.keys(data[0])[1];

        // Create scales
        const x = d3.scaleBand()
            .range([0, width])
            .domain(data.map(d => d[xField]))
            .padding(0.2);

        const y = d3.scaleLinear()
            .range([height, 0])
            .domain([0, d3.max(data, d => d[yField]) || 0])
            .nice();

        // Add axes
        g.append("g")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x))
            .selectAll("text")
            .attr("transform", "translate(-8,8)rotate(-35)")
            .style("text-anchor", "end")
            .style("font-size", "11px");

        g.append("g").call(d3.axisLeft(y));

        // Add bars
        g.selectAll(".bar")
            .data(data)
            .enter()
            .append("rect")
            .attr("class", "bar")
            .attr("x", d => x(d[xField]))
            .attr("y", d => y(d[yField]))
            .attr("width", x.bandwidth())
            .attr("height", d => height - y(d[yField]))
            .style("fill", options.color || "#4299e1")
            .on("mouseover", (event, d) => {
                tooltip.style("opacity", .9);
                tooltip.html(`<strong>${d[xField]}</strong>: ${d[yField]}`)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", () => {
                tooltip.style("opacity", 0);
            });
    },

    renderLineChart: function(g, data, options, width, height, tooltip) {
        const xField = options.x_field || Object.keys(data[0])[0];
        const yField = options.y_field || Object.keys(data[0])[1];

        // Create scales - using scalePoint for x-axis like the working reference
        const x = d3.scalePoint()
            .range([0, width])
            .domain(data.map(d => d[xField]))
            .padding(0.5);

        const y = d3.scaleLinear()
            .range([height, 0])
            .domain([0, d3.max(data, d => d[yField]) || 0])
            .nice();

        // Add axes
        g.append("g")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x))
            .selectAll("text")
            .style("font-size", "11px")
            .attr("transform", "translate(-10,0)rotate(-45)")
            .style("text-anchor", "end");

        g.append("g").call(d3.axisLeft(y));

        // Create line generator
        const line = d3.line()
            .x(d => x(d[xField]))
            .y(d => y(d[yField]));

        // Add the line
        g.append("path")
            .datum(data)
            .attr("class", "line")
            .attr("d", line)
            .style("stroke", options.color || "#4299e1")
            .style("stroke-width", 2)
            .style("fill", "none");

        // Add dots
        g.selectAll(".chart-dot")
            .data(data)
            .enter()
            .append("circle")
            .attr("class", "chart-dot")
            .attr("cx", d => x(d[xField]))
            .attr("cy", d => y(d[yField]))
            .attr("r", 4)
            .style("fill", options.color || "#4299e1")
            .style("opacity", 0.8)
            .style("position", "static")
            .style("transform", "none")
            .on("mouseover", (event, d) => {
                tooltip.style("opacity", .9);
                tooltip.html(`<strong>${d[xField]}</strong>: ${d[yField]}`)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 10) + "px");
            })
            .on("mouseout", () => {
                tooltip.style("opacity", 0);
            });
    },

    renderScatterPlot: function(g, data, options, width, height, tooltip) {
        const xField = options.x_field || Object.keys(data[0])[0];
        const yField = options.y_field || Object.keys(data[0])[1];

        // Create scales
        const x = d3.scaleLinear()
            .range([0, width])
            .domain(d3.extent(data, d => d[xField]))
            .nice();

        const y = d3.scaleLinear()
            .range([height, 0])
            .domain(d3.extent(data, d => d[yField]))
            .nice();

        const sizeScale = options.size_field ? 
            d3.scaleLinear().range([3, 15]).domain(d3.extent(data, d => d[options.size_field]) || [1,1]) : 
            () => 5;

        // Add axes
        g.append("g")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x));

        g.append("g").call(d3.axisLeft(y));

        // Add points
        g.selectAll(".chart-scatter-dot")
            .data(data)
            .enter()
            .append("circle")
            .attr("class", "chart-scatter-dot")
            .attr("cx", d => x(d[xField]))
            .attr("cy", d => y(d[yField]))
            .attr("r", d => options.size_field ? sizeScale(d[options.size_field]) : 5)
            .style("fill", options.color || "#4299e1")
            .style("opacity", 0.7)
            .style("position", "static")
            .style("transform", "none")
            .on("mouseover", (event, d) => {
                tooltip.style("opacity", .9);
                let tipHtml = `<strong>X:</strong> ${d[xField]}<br/><strong>Y:</strong> ${d[yField]}`;
                if (options.size_field) tipHtml += `<br/><strong>Size:</strong> ${d[options.size_field]}`;
                tooltip.html(tipHtml)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 10) + "px");
            })
            .on("mouseout", () => {
                tooltip.style("opacity", 0);
            });
    },

    renderPieChart: function(g, data, options, width, height, tooltip) {
        const valueField = options.value_field || 'value';
        const labelField = options.label_field || 'label';
        
        const radius = Math.min(width, height) / 2;
        g.attr("transform", `translate(${width / 2 + 40},${height / 2 + 30})`);

        const color = d3.scaleOrdinal()
            .range(options.colors || d3.schemeSet2);

        const pie = d3.pie()
            .value(d => d[valueField]);
        
        const data_ready = pie(data);
        const arc = d3.arc()
            .innerRadius(0)
            .outerRadius(radius);

        // Add pie slices
        g.selectAll('path')
            .data(data_ready)
            .enter()
            .append('path')
            .attr('d', arc)
            .attr('fill', d => color(d.data[labelField]))
            .attr("stroke", "white")
            .style("stroke-width", "2px")
            .style("opacity", 0.8)
            .on("mouseover", (event, d) => {
                tooltip.style("opacity", .9);
                tooltip.html(`<strong>${d.data[labelField]}</strong>: ${d.data[valueField]}`)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseout", () => {
                tooltip.style("opacity", 0);
            });
    }
};