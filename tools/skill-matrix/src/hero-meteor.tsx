import { useEffect, useRef } from "react";

const vertexSource = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}`;

const fragmentSource = `#version 300 es
precision highp float;
uniform vec2 resolution;
uniform float time;
out vec4 color;

void main() {
  vec2 point = gl_FragCoord.xy / resolution;
  float behind = point.x;
  float vertical = point.y - 0.5;
  float mask = step(0.0, behind);
  float head = exp(-pow(behind * 65.0, 2.0) - pow(vertical * 6.0, 2.0));
  float tail = exp(-behind * 3.5) * exp(-pow(vertical * 14.0, 2.0));
  float flow = 0.55 + 0.45 * pow(0.5 + 0.5 * sin(behind * 30.0 - time * 7.0), 2.0);
  float glow = exp(-behind * 9.0) * exp(-pow(vertical * 5.0, 2.0));
  float alpha = mask * clamp(head * 0.9 + tail * flow * 0.72 + glow * 0.2, 0.0, 0.98);
  vec3 gold = vec3(0.93, 0.69, 0.46);
  vec3 light = vec3(1.0, 0.96, 0.81);
  color = vec4(mix(gold, light, head), alpha);
}`;

function createShader(gl: WebGL2RenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return shader;
  console.warn("Hero 陨石着色器编译失败", gl.getShaderInfoLog(shader));
  gl.deleteShader(shader);
  return null;
}

export function HeroMeteor() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (motion.matches) return;

    const gl = canvas.getContext("webgl2", { alpha: true, antialias: false, premultipliedAlpha: false });
    if (!gl) return;
    const vertex = createShader(gl, gl.VERTEX_SHADER, vertexSource);
    const fragment = createShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
    if (!vertex || !fragment) {
      if (vertex) gl.deleteShader(vertex);
      if (fragment) gl.deleteShader(fragment);
      return;
    }
    const program = gl.createProgram();
    const buffer = gl.createBuffer();
    if (!program || !buffer) {
      gl.deleteShader(vertex);
      gl.deleteShader(fragment);
      if (program) gl.deleteProgram(program);
      if (buffer) gl.deleteBuffer(buffer);
      return;
    }
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    gl.deleteShader(vertex);
    gl.deleteShader(fragment);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.warn("Hero 陨石着色器链接失败", gl.getProgramInfoLog(program));
      gl.deleteProgram(program);
      gl.deleteBuffer(buffer);
      return;
    }

    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, "position");
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    const resolution = gl.getUniformLocation(program, "resolution");
    const time = gl.getUniformLocation(program, "time");
    const started = performance.now();
    let frame = 0;
    let isLost = false;

    const resize = () => {
      const scale = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(canvas.clientWidth * scale);
      canvas.height = Math.round(canvas.clientHeight * scale);
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(resolution, canvas.width, canvas.height);
    };
    const draw = (now: number) => {
      gl.uniform1f(time, (now - started) / 1000);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      frame = requestAnimationFrame(draw);
    };
    const sync = () => {
      cancelAnimationFrame(frame);
      canvas.style.opacity = motion.matches || isLost ? "0" : "1";
      if (motion.matches || document.hidden || isLost) return;
      resize();
      frame = requestAnimationFrame(draw);
    };
    const onContextLost = (event: Event) => {
      event.preventDefault();
      isLost = true;
      sync();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    motion.addEventListener("change", sync);
    document.addEventListener("visibilitychange", sync);
    canvas.addEventListener("webglcontextlost", onContextLost);
    sync();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      motion.removeEventListener("change", sync);
      document.removeEventListener("visibilitychange", sync);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
    };
  }, []);

  return <span className="heroMeteor" aria-hidden="true"><canvas ref={canvasRef} /></span>;
}
