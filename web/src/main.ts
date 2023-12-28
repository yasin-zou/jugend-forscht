import {
  Application,
  BaseTexture,
  Assets,
  Rectangle,
  Sprite,
  Texture,
  Graphics,
} from "pixi.js";

import "./index.css";

const $ = document.querySelector.bind(document);

let listener: ((e: MouseEvent) => void) | null = null;

let scale = 1;

function getBase64(file: File): Promise<string | ArrayBuffer | null> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => resolve(reader.result);
    reader.onerror = (error) => reject(error);
  });
}
let background: Sprite | null = null;

let height = window.innerHeight;
height -= parseInt(getComputedStyle($("#controls")!).height);

const app = new Application({
  width: window.innerWidth,
  height: height,
  backgroundColor: 0xffffff,
});

document.body.appendChild(app.view);

const circles: Graphics[] = [];

function makeCircle(
  size: number,
  color: number | null = null,
  interactive: boolean = true,
): Graphics {
  const circle = new Graphics();
  circle.beginFill(color ?? 0xff0000);
  circle.drawCircle(0, 0, size);
  circle.endFill();

  circle.tint = 0xff0000;
  app.stage.addChild(circle);
  circle.interactive = interactive;
  // @ts-expect-error
  circle.dragging = false;

  if (!interactive) {
    return circle;
  }

  circle.on("mousedown", (e) => {
    console.log("Picked up");

    listener = (e: MouseEvent) => {
      circle.x += e.movementX;
      circle.y += e.movementY;
    };

    document.addEventListener("mousemove", listener!);
  });

  circle.on("mouseup", (e) => {
    console.log("Moving");

    circle.x += e.movementX;
    circle.y += e.movementY;
    document.removeEventListener("mousemove", listener!);
  });

  return circle;
}

$<HTMLInputElement>("#file")!.oninput = async (e) => {
  if (background) {
    app.stage.removeChild(background);
  }
  const data = await getBase64(
    (e.currentTarget! as HTMLInputElement).files![0],
  );
  if (typeof data !== "string") {
    return;
  }
  const texture = BaseTexture.from(data);
  await new Promise((resolve) => {
    texture.on("loaded", resolve);
  });
  console.table({ width: texture.width, height: texture.height });
  let ratio = app.screen.height / texture.height;

  if (ratio * texture.width > app.screen.width) {
    ratio = app.screen.width / texture.width;
  }

  background = Sprite.from(texture, {});
  background.width = texture.width * ratio;
  background.height = texture.height * ratio;

  app.stage.addChildAt(background, 0);
};

$<HTMLInputElement>("#add")!.onclick = () => {
  circles.push(makeCircle(25));
};

$<HTMLInputElement>("#load-config")!.onclick = () => {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json";
  input.oninput = async (e) => {
    const data = await getBase64(
      (e.currentTarget! as HTMLInputElement).files![0],
    );
    if (typeof data !== "string") {
      return;
    }
    const json = JSON.parse(atob(data.split(",")[1]));
    const { positions } = json;

    if (background) {
      app.stage.removeChild(background);
    }

    circles.forEach((rectangle) => {
      app.stage.removeChild(rectangle);
    });

    circles.length = 0;

    positions.forEach((position: { x: number; y: number }) => {
      const rectangle = makeCircle(25);
      rectangle.x = position.x * scale - rectangle.width / 2;
      rectangle.y = position.y * scale - rectangle.height / 2;
      circles.push(rectangle);
    });
  };
  input.click();
};

$<HTMLInputElement>("#load-results")!.onclick = () => {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json";
  input.oninput = async (e) => {
    const data = await getBase64(
      (e.currentTarget! as HTMLInputElement).files![0],
    );
    if (typeof data !== "string") {
      return;
    }
    const json = JSON.parse(atob(data.split(",")[1]));

    for (let i = 0; i < json.length; i++) {
      // values are in meters use scale (pixels per meter) to convert to back to pixels
      const result = makeCircle(10, 0x00ff00, false);
      result.tint = 0x00ff00;
      result.alpha = 0.2;
      result.x = json[i][0] * scale - result.width / 2;
      result.y = json[i][1] * scale - result.height / 2;
    }
  };
  input.click();
};

$<HTMLInputElement>("#delete-results")!.onclick = () => {
  app.stage.children.forEach((child) => {
    if (child.tint === 0x00ff00) {
      app.stage.removeChild(child);
    }
  });
};

$<HTMLInputElement>("#save")!.onclick = () => {
  let positions = circles.map((rectangle) => {
    // Gebe die Mitte des Rechtecks zurück

    // Gebe x als Meter zurück
    const x = (rectangle.x + rectangle.width / 2) / scale;
    const y = (rectangle.y + rectangle.height / 2) / scale;

    return {
      x,
      y,
    };
  });

  positions = positions.sort((a, b) => a.x - b.x);
  // --> Eindeutige Zuordnung der Rechtecke, sortiert nach x-Koordinate

  const data = {
    positions,
    meta: {
      width: window.innerWidth,
      height: window.innerHeight,
    },
  };

  download("konfig.json", data);
};

function waitForMouseClick(): Promise<MouseEvent> {
  return new Promise((resolve) => {
    const listener = (e: MouseEvent) => {
      document.removeEventListener("mousedown", listener);
      resolve(e);
    };
    document.addEventListener("mousedown", listener);
  });
}

$<HTMLInputElement>("#select-two")!.onclick = async () => {
  const first = await waitForMouseClick();
  const second = await waitForMouseClick();

  // ask user for distance of two points
  const distance = parseFloat(prompt("Distance in meters")!);
  const pixelDistance = Math.sqrt(
    (first.clientX - second.clientX) ** 2 +
      (first.clientY - second.clientY) ** 2,
  );

  scale = pixelDistance / distance;

  $("#skalierung")!.innerHTML = `${Math.round(scale * 100) / 100} px/m`;
};

function download(filename: string, json: any) {
  const element = document.createElement("a");
  element.setAttribute(
    "href",
    "data:text/plain;charset=utf-8," + encodeURIComponent(JSON.stringify(json)),
  );
  element.setAttribute("download", filename);

  element.style.display = "none";
  document.body.appendChild(element);

  element.click();

  document.body.removeChild(element);
}

// @ts-expect-error
window.setScale = (newScale: number) => {
  scale = newScale;
  $("#skalierung")!.innerHTML = `${Math.round(scale * 100) / 100} px/m`;
};
