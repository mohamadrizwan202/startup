(() => {
  'use strict';

  const CARD_WIDTH = 1080;
  const CARD_HEIGHT = 1350;
  const BRAND_URL = 'https://purefyul.com/app?utm_source=share_card&utm_medium=qr';
  const BRAND_GREEN = '#0B3D34';
  const BRAND_TEAL = '#1F7A6B';
  const CARD_BACKGROUND = '#F7F2E7';

  const QR_ROWS = [
    '111111101111111010111111001111111',
    '100000101011110011100101001000001',
    '101110100111100100101011101011101',
    '101110101110001001010010001011101',
    '101110100010001001010100101011101',
    '100000100011000010011010101000001',
    '111111101010101010101010101111111',
    '000000001100100101100011000000000',
    '101101110111101001100100001001011',
    '000111010110100110010111001101101',
    '001000100110101011100011101111011',
    '110011001011011000011010100101011',
    '111011101110000011010000110111000',
    '101000001101100111010000110101010',
    '110011110110010000011000101011100',
    '110000000001010100111111111111100',
    '011110111000001000111111011011100',
    '111110011101111101101011101011001',
    '001111101001011100101010100110110',
    '110111011000111011110000000010011',
    '110010101111101001101100000001100',
    '101011001001101010001011001001101',
    '001111110111010011000011101110011',
    '011101000101001000011011110010010',
    '100001111100100011110001111111011',
    '000000001101010111110000100011010',
    '111111101011000000111001101010000',
    '100000101001001110010111100011111',
    '101110100101110010101111111110110',
    '101110101000001111001101000101101',
    '101110101011001111000011111101100',
    '100000100000001011100000011110001',
    '111111101011001101110101000011100'
  ];

  const COLOR_PROFILES = [
    {
      terms: ['blueberry', 'blackberry', 'acai', 'purple grape'],
      rgb: [100, 59, 145],
      strength: 1.75
    },
    {
      terms: ['strawberry', 'raspberry', 'cranberry', 'cherry', 'pomegranate', 'beet'],
      rgb: [190, 54, 82],
      strength: 1.55
    },
    {
      terms: ['mango', 'pineapple', 'orange', 'peach', 'apricot', 'papaya', 'passion fruit'],
      rgb: [235, 154, 64],
      strength: 1.25
    },
    {
      terms: ['guava', 'watermelon', 'pink grapefruit', 'dragon fruit'],
      rgb: [219, 103, 108],
      strength: 1.3
    },
    {
      terms: ['spinach', 'kale', 'matcha', 'parsley', 'mint', 'avocado', 'celery'],
      rgb: [75, 128, 76],
      strength: 1.65
    },
    {
      terms: ['cocoa', 'cacao', 'chocolate', 'coffee'],
      rgb: [103, 70, 54],
      strength: 1.55
    },
    {
      terms: ['peanut butter', 'almond butter', 'cashew butter', 'hazelnut', 'walnut', 'pecan'],
      rgb: [166, 116, 69],
      strength: 0.9
    },
    {
      terms: ['banana', 'pear', 'apple', 'oats', 'oat'],
      rgb: [218, 194, 128],
      strength: 0.5,
      cream: 0.08
    },
    {
      terms: ['milk', 'yogurt', 'kefir', 'cream'],
      rgb: [239, 234, 221],
      strength: 0.16,
      cream: 0.26
    }
  ];

  function safeText(value) {
    return String(value ?? '').replace(/\s+/g, ' ').trim();
  }

  function escapeXml(value) {
    return safeText(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&apos;');
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function mixRgb(first, second, ratio) {
    const amount = clamp(Number(ratio) || 0, 0, 1);
    return first.map((channel, index) => (
      Math.round(channel + (second[index] - channel) * amount)
    ));
  }

  function rgbToHex(rgb) {
    return `#${rgb.map(channel => (
      clamp(Math.round(channel), 0, 255).toString(16).padStart(2, '0')
    )).join('')}`;
  }

  function parseIngredientAmount(ingredient) {
    const direct = Number(
      ingredient?.amount ??
      ingredient?.totalGrams ??
      ingredient?.nutritionWeightG
    );

    if (Number.isFinite(direct) && direct > 0) {
      return direct;
    }

    const servingMatch = safeText(ingredient?.serving).match(/\d+(?:\.\d+)?/);
    return servingMatch ? Number(servingMatch[0]) : 80;
  }

  function getSmoothieColors(ingredients) {
    const weighted = [0, 0, 0];
    let totalWeight = 0;
    let creaminess = 0;

    (Array.isArray(ingredients) ? ingredients : []).forEach(ingredient => {
      const name = safeText(ingredient?.name).toLowerCase();
      const profile = COLOR_PROFILES.find(candidate => (
        candidate.terms.some(term => name.includes(term))
      ));

      if (!profile) {
        return;
      }

      const portion = clamp(parseIngredientAmount(ingredient), 5, 450);
      const weight = Math.sqrt(portion) * profile.strength;

      profile.rgb.forEach((channel, index) => {
        weighted[index] += channel * weight;
      });

      totalWeight += weight;
      creaminess += (profile.cream || 0) * clamp(portion / 240, 0.2, 1);
    });

    let base = totalWeight > 0
      ? weighted.map(channel => channel / totalWeight)
      : [207, 113, 93];

    base = mixRgb(base, [244, 237, 221], clamp(creaminess, 0, 0.34));

    return {
      base: rgbToHex(base),
      top: rgbToHex(mixRgb(base, [255, 255, 255], 0.22)),
      bottom: rgbToHex(mixRgb(base, [54, 43, 39], 0.24)),
      accent: rgbToHex(mixRgb(base, [255, 255, 255], 0.72))
    };
  }

  function measureText(text, font) {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    context.font = font;
    return context.measureText(safeText(text)).width;
  }

  function wrapText(text, maxWidth, font, maxLines = 3) {
    const words = safeText(text).split(' ').filter(Boolean);
    const lines = [];
    let current = '';

    words.forEach(word => {
      const candidate = current ? `${current} ${word}` : word;

      if (!current || measureText(candidate, font) <= maxWidth) {
        current = candidate;
        return;
      }

      lines.push(current);
      current = word;
    });

    if (current) {
      lines.push(current);
    }

    if (lines.length <= maxLines) {
      return lines;
    }

    const limited = lines.slice(0, maxLines);
    let finalLine = limited[maxLines - 1];

    while (
      finalLine.length > 1 &&
      measureText(`${finalLine}…`, font) > maxWidth
    ) {
      finalLine = finalLine.slice(0, -1).trim();
    }

    limited[maxLines - 1] = `${finalLine}…`;
    return limited;
  }

  function svgTextLines(
    lines,
    x,
    y,
    lineHeight,
    attributes
  ) {
    const source =
      Array.isArray(lines)
        ? lines
        : [];

    return source
      .map((line, index) => {
        const safeLine =
          escapeXml(
            String(line ?? '')
          );

        const lineY =
          Number(y) +
          index * Number(lineHeight);

        return (
          `<text x="${x}" y="${lineY}" ` +
          `${attributes}>${safeLine}</text>`
        );
      })
      .join('');
  }

  function buildQrSvg(x, y, size) {
    const quietZone = 4;
    const moduleCount = QR_ROWS.length;
    const cell = size / (moduleCount + quietZone * 2);
    let modules = '';

    QR_ROWS.forEach((row, rowIndex) => {
      row.split('').forEach((value, columnIndex) => {
        if (value !== '1') {
          return;
        }

        modules += `<rect x="${(
          x + (columnIndex + quietZone) * cell
        ).toFixed(2)}" y="${(
          y + (rowIndex + quietZone) * cell
        ).toFixed(2)}" width="${cell.toFixed(2)}" height="${cell.toFixed(2)}" fill="${BRAND_GREEN}"/>`;
      });
    });

    return `
      <rect x="${x}" y="${y}" width="${size}" height="${size}" rx="18" fill="#FFFFFF"/>
      ${modules}
    `;
  }

  function truncateShareLabel(
    value,
    maxLength = 28
  ) {
    const label = safeText(value);

    if (label.length <= maxLength) {
      return label;
    }

    return (
      `${label.slice(0, maxLength - 1).trim()}…`
    );
  }

  function normalizeAllergenTitle(value) {
    const title = safeText(value);

    if (
      /^no major allergens identified/i.test(
        title
      )
    ) {
      return 'No major allergens identified';
    }

    return (
      title ||
      'Review ingredients for allergen details'
    );
  }

  function buildPremiumBotanical(
    ingredients
  ) {
    /*
     * Top-right editorial smoothie-pour composition.
     * Uses fixed PureFyul brand styling only.
     * No ingredient-color guessing or external assets.
     */
    void ingredients;

    return `
      <!-- Top-right editorial smoothie-pour composition -->
      <g transform="translate(1080 0) scale(1.22 1) translate(-1080 0)">
        <!-- Soft corner field -->
        <path
          d="
            M1080 0
            H820
            C760 110 752 236 788 344
            C825 453 920 532 1080 576
            Z
          "
          fill="#F2EBDD"
          opacity="0.92"
        />

        <!-- Main outer pour -->
        <path
          d="
            M1080 34
            C1028 44 989 76 964 120
            C935 171 931 230 948 287
            C963 340 989 384 1028 430
            C1046 452 1062 479 1072 512
            L1080 512
            Z
          "
          fill="#DDE4D8"
          opacity="0.96"
        />

        <!-- Inner smoothie layer -->
        <path
          d="
            M1080 78
            C1042 88 1012 114 995 151
            C975 194 975 240 988 283
            C1000 324 1024 362 1053 395
            C1064 408 1073 424 1080 447
            Z
          "
          fill="#0E5A52"
          opacity="0.88"
        />

        <!-- Berry-plum accent pool -->
        <path
          d="
            M1080 352
            C1058 347 1035 351 1017 363
            C998 375 987 394 985 415
            C983 438 992 458 1008 474
            C1026 492 1050 503 1080 509
            Z
          "
          fill="#D8C3B9"
          opacity="0.78"
        />

        <!-- Cream highlight ribbon -->
        <path
          d="
            M1080 104
            C1048 112 1025 134 1014 165
            C1001 200 1002 236 1012 269
            C1022 301 1040 329 1062 352
            C1068 359 1074 368 1080 381
          "
          fill="none"
          stroke="#FFF9F0"
          stroke-width="2.2"
          stroke-linecap="round"
          opacity="0.74"
        />

        <!-- Warm editorial seam -->
        <path
          d="
            M1080 56
            C1036 67 1002 95 981 136
            C956 185 952 243 968 298
            C982 347 1007 389 1042 430
            C1054 444 1064 460 1072 480
          "
          fill="none"
          stroke="#C7A35D"
          stroke-width="1.8"
          stroke-linecap="round"
          opacity="0.82"
        />

        <!-- Soft lower tint -->
        <ellipse
          cx="1038"
          cy="496"
          rx="52"
          ry="42"
          fill="#C9D4C4"
          opacity="0.55"
        />
      </g>
    `;
  }

  function buildEditorialTitleLines(
    name,
    fontSize
  ) {
    const words =
      safeText(name)
        .split(/\s+/)
        .filter(Boolean);

    // Match the approved editorial demo:
    // two- and three-word names stack word by word.
    if (
      words.length === 2 ||
      words.length === 3
    ) {
      return words;
    }

    return wrapText(
      name,
      410,
      (
        `400 ${fontSize}px ` +
        '"Bodoni 72"'
      ),
      3
    );
  }

  function buildMetricIcon(
    kind,
    centerX,
    centerY
  ) {
    const type =
      String(kind || '')
        .trim()
        .toLowerCase();

    const badge = '#0D4F47';
    const cream = '#F8F5EC';
    const gold = '#D2B36F';

    const background = `
      <circle
        cx="${centerX}"
        cy="${centerY}"
        r="20"
        fill="${badge}"
      />
    `;

    if (type === 'calories') {
      return `
        ${background}

        <!-- PureFyul fuel-gauge icon -->
        <path
          d="
            M${centerX - 12} ${centerY + 7}
            C${centerX - 12} ${centerY - 1}
             ${centerX - 7} ${centerY - 9}
             ${centerX} ${centerY - 11}
            C${centerX + 7} ${centerY - 9}
             ${centerX + 12} ${centerY - 1}
             ${centerX + 12} ${centerY + 7}
          "
          fill="none"
          stroke="${cream}"
          stroke-width="2.2"
          stroke-linecap="round"
        />

        <line
          x1="${centerX}"
          y1="${centerY + 5}"
          x2="${centerX + 7}"
          y2="${centerY - 5}"
          stroke="${cream}"
          stroke-width="2.5"
          stroke-linecap="round"
        />

        <circle
          cx="${centerX}"
          cy="${centerY + 5}"
          r="3"
          fill="${gold}"
        />

        <line
          x1="${centerX - 9}"
          y1="${centerY + 1}"
          x2="${centerX - 6}"
          y2="${centerY + 1}"
          stroke="${cream}"
          stroke-width="1.6"
          stroke-linecap="round"
        />

        <line
          x1="${centerX}"
          y1="${centerY - 8}"
          x2="${centerX}"
          y2="${centerY - 5}"
          stroke="${cream}"
          stroke-width="1.6"
          stroke-linecap="round"
        />

        <line
          x1="${centerX + 7}"
          y1="${centerY - 3}"
          x2="${centerX + 9}"
          y2="${centerY - 1}"
          stroke="${gold}"
          stroke-width="1.7"
          stroke-linecap="round"
        />
      `;
    }

    if (type === 'protein') {
      return `
        ${background}

        <!-- PureFyul protein building-block icon -->
        <rect
          x="${centerX - 12}"
          y="${centerY - 10}"
          width="10"
          height="8"
          rx="2.5"
          fill="none"
          stroke="${cream}"
          stroke-width="2"
        />

        <rect
          x="${centerX + 2}"
          y="${centerY - 10}"
          width="10"
          height="8"
          rx="2.5"
          fill="none"
          stroke="${cream}"
          stroke-width="2"
        />

        <rect
          x="${centerX - 5}"
          y="${centerY + 3}"
          width="10"
          height="8"
          rx="2.5"
          fill="none"
          stroke="${cream}"
          stroke-width="2"
        />

        <line
          x1="${centerX - 7}"
          y1="${centerY - 2}"
          x2="${centerX - 1}"
          y2="${centerY + 3}"
          stroke="${cream}"
          stroke-width="1.7"
          stroke-linecap="round"
        />

        <line
          x1="${centerX + 7}"
          y1="${centerY - 2}"
          x2="${centerX + 1}"
          y2="${centerY + 3}"
          stroke="${cream}"
          stroke-width="1.7"
          stroke-linecap="round"
        />

        <circle
          cx="${centerX}"
          cy="${centerY}"
          r="2.6"
          fill="${gold}"
        />
      `;
    }

    if (type === 'fiber') {
      return `
        ${background}

        <!-- PureFyul woven-fiber icon -->
        <path
          d="
            M${centerX - 9} ${centerY - 13}
            C${centerX - 2} ${centerY - 8}
             ${centerX - 2} ${centerY - 3}
             ${centerX - 9} ${centerY + 2}
            C${centerX - 14} ${centerY + 6}
             ${centerX - 10} ${centerY + 11}
             ${centerX - 5} ${centerY + 14}
          "
          fill="none"
          stroke="${cream}"
          stroke-width="2.1"
          stroke-linecap="round"
        />

        <path
          d="
            M${centerX} ${centerY - 14}
            C${centerX + 7} ${centerY - 9}
             ${centerX + 7} ${centerY - 3}
             ${centerX} ${centerY + 2}
            C${centerX - 5} ${centerY + 6}
             ${centerX - 1} ${centerY + 11}
             ${centerX + 4} ${centerY + 14}
          "
          fill="none"
          stroke="${cream}"
          stroke-width="2.1"
          stroke-linecap="round"
        />

        <path
          d="
            M${centerX + 9} ${centerY - 13}
            C${centerX + 2} ${centerY - 8}
             ${centerX + 2} ${centerY - 3}
             ${centerX + 9} ${centerY + 2}
            C${centerX + 14} ${centerY + 6}
             ${centerX + 10} ${centerY + 11}
             ${centerX + 5} ${centerY + 14}
          "
          fill="none"
          stroke="${cream}"
          stroke-width="2.1"
          stroke-linecap="round"
        />

        <line
          x1="${centerX - 8}"
          y1="${centerY - 4}"
          x2="${centerX + 8}"
          y2="${centerY - 4}"
          stroke="${gold}"
          stroke-width="1.5"
          stroke-linecap="round"
        />

        <line
          x1="${centerX - 8}"
          y1="${centerY + 6}"
          x2="${centerX + 8}"
          y2="${centerY + 6}"
          stroke="${gold}"
          stroke-width="1.5"
          stroke-linecap="round"
        />
      `;
    }

    return `
      ${background}

      <!-- PureFyul measured-sugar icon -->
      <path
        d="
          M${centerX - 12} ${centerY + 4}
          C${centerX - 8} ${centerY - 3}
           ${centerX + 2} ${centerY - 4}
           ${centerX + 6} ${centerY + 2}
          C${centerX + 2} ${centerY + 9}
           ${centerX - 7} ${centerY + 10}
           ${centerX - 12} ${centerY + 4}
          Z
        "
        fill="none"
        stroke="${cream}"
        stroke-width="2.2"
        stroke-linejoin="round"
      />

      <path
        d="
          M${centerX + 5} ${centerY + 2}
          L${centerX + 13} ${centerY - 5}
        "
        fill="none"
        stroke="${cream}"
        stroke-width="2.4"
        stroke-linecap="round"
      />

      <circle
        cx="${centerX - 5}"
        cy="${centerY + 1}"
        r="2"
        fill="${gold}"
      />

      <circle
        cx="${centerX}"
        cy="${centerY + 3}"
        r="1.8"
        fill="${cream}"
      />

      <circle
        cx="${centerX - 1}"
        cy="${centerY - 2}"
        r="1.7"
        fill="${gold}"
      />
    `;
  }

  function buildMetricCards(nutrition) {
    const metrics = [
      {
        key: 'calories',
        label: 'Calories',
        value: `${Math.round(
          Number(nutrition?.calories) || 0
        )}`,
        unit: 'kcal'
      },
      {
        key: 'protein',
        label: 'Protein',
        value: `${(
          Number(nutrition?.protein) || 0
        ).toFixed(1)}`,
        unit: 'g'
      },
      {
        key: 'fiber',
        label: 'Fiber',
        value: `${(
          Number(nutrition?.fiber) || 0
        ).toFixed(1)}`,
        unit: 'g'
      },
      {
        key: 'sugar',
        label: 'Sugar',
        value: `${(
          Number(nutrition?.sugar) || 0
        ).toFixed(1)}`,
        unit: 'g'
      }
    ];

    return metrics
      .map((metric, index) => {
        const x = 64 + index * 244;

        return `
          <rect
            x="${x}"
            y="660"
            width="220"
            height="176"
            rx="23"
            fill="#FFFDF8"
            stroke="#E3DACE"
            filter="url(#pf-soft-shadow)"
          />

          ${buildMetricIcon(
            metric.key,
            x + 35,
            703
          )}

          <text
            x="${x + 65}"
            y="710"
            font-family="Arial, sans-serif"
            font-size="19"
            font-weight="600"
            fill="${BRAND_GREEN}"
          >${metric.label}</text>

          <text
            x="${x + 26}"
            y="784"
            font-family="
              'Bodoni 72',
              Didot,
              'Iowan Old Style',
              'Times New Roman',
              Georgia,
              serif
            "
            font-size="53"
            font-weight="400"
            fill="${BRAND_GREEN}"
          >${escapeXml(metric.value)}</text>

          <text
            x="${x + 26}"
            y="816"
            font-family="Arial, sans-serif"
            font-size="19"
            font-weight="500"
            fill="#64716B"
          >${metric.unit}</text>
        `;
      })
      .join('');
  }

  function buildIngredientRows(ingredients) {
    const source =
      Array.isArray(ingredients)
        ? ingredients
        : [];

    const visible = source
      .slice(0, 8)
      .map(ingredient => {
        const rawName =
          safeText(
            ingredient?.name || 'Ingredient'
          ).trim();

        /*
         * Capitalize only the first character:
         * oats -> Oats
         * greek yogurt -> Greek yogurt
         */
        const capitalizedName =
          rawName
            ? (
                rawName.charAt(0).toUpperCase()
                + rawName.slice(1)
              )
            : 'Ingredient';

        return {
          name: truncateShareLabel(
            capitalizedName,
            24
          ),
          serving: truncateShareLabel(
            ingredient?.serving || '',
            13
          )
        };
      });

    if (source.length > 8) {
      visible[7] = {
        name: `+${source.length - 7} more ingredients`,
        serving: ''
      };
    }

    const rowGap =
      visible.length <= 5
        ? 36
        : (
            visible.length === 6
              ? 31
              : 27
          );

    return visible
      .map((ingredient, index) => {
        const y = 936 + index * rowGap;

        /*
         * Approximate the label width so the dotted
         * leader begins after the ingredient name.
         */
        const estimatedNameWidth =
          Math.min(
            224,
            ingredient.name.length * 9.2
          );

        const leaderStart =
          Math.min(
            920,
            Math.max(
              756,
              626 + estimatedNameWidth + 18
            )
          );

        return `
          <!-- Premium ingredient row -->
          <text
            x="626"
            y="${y}"
            font-family="Arial, sans-serif"
            font-size="18"
            font-weight="500"
            fill="#123F3A"
          >${escapeXml(ingredient.name)}</text>

          <line
            x1="${leaderStart}"
            y1="${y - 5}"
            x2="952"
            y2="${y - 5}"
            stroke="#D4CEC2"
            stroke-width="1.2"
            stroke-dasharray="2.5 6"
            stroke-linecap="round"
            opacity="0.82"
          />

          <text
            x="1014"
            y="${y}"
            text-anchor="end"
            font-family="Arial, sans-serif"
            font-size="18"
            font-weight="600"
            font-feature-settings="'tnum' 1"
            fill="#52615B"
          >${escapeXml(ingredient.serving)}</text>
        `;
      })
      .join('');
  }

  function buildAllergenStrip(allergenTitle) {
    const title =
      safeText(allergenTitle)
      || 'Review selected ingredients';

    const isClear =
      /^no major allergens identified/i.test(
        title
      );

    const surfaceStart =
      isClear
        ? '#F5F8F1'
        : '#FFF9EE';

    const surfaceEnd =
      isClear
        ? '#E9F0E5'
        : '#F4E8D5';

    const border =
      isClear
        ? '#BFCDBA'
        : '#D9C39A';

    const accent =
      isClear
        ? '#83A58A'
        : '#C7A45F';

    const microLabel =
      isClear
        ? 'INGREDIENT TRACE'
        : 'ALLERGEN TRACE';

    return `
      <defs>
        <linearGradient
          id="pf-allergen-ribbon-surface"
          x1="0"
          y1="0"
          x2="1"
          y2="1"
        >
          <stop
            offset="0%"
            stop-color="${surfaceStart}"
          />

          <stop
            offset="100%"
            stop-color="${surfaceEnd}"
          />
        </linearGradient>

        <linearGradient
          id="pf-allergen-ribbon-tab"
          x1="0"
          y1="0"
          x2="1"
          y2="1"
        >
          <stop
            offset="0%"
            stop-color="#0D5A51"
          />

          <stop
            offset="100%"
            stop-color="#083F3A"
          />
        </linearGradient>
      </defs>

      <!-- Ingredient Trace Ribbon surface -->
      <rect
        x="64"
        y="1123"
        width="952"
        height="76"
        rx="23"
        fill="url(#pf-allergen-ribbon-surface)"
        stroke="${border}"
        stroke-width="1.3"
      />

      <!-- Integrated asymmetric trace tab -->
      <path
        d="
          M87 1123
          H147
          L174 1161
          L147 1199
          H87
          C74 1199 64 1189 64 1176
          V1146
          C64 1133 74 1123 87 1123
          Z
        "
        fill="url(#pf-allergen-ribbon-tab)"
      />

      <!-- Quiet accent seam -->
      <line
        x1="154"
        y1="1143"
        x2="167"
        y2="1161"
        stroke="${accent}"
        stroke-width="2"
        stroke-linecap="round"
        opacity="0.85"
      />

      <line
        x1="167"
        y1="1161"
        x2="154"
        y2="1179"
        stroke="${accent}"
        stroke-width="2"
        stroke-linecap="round"
        opacity="0.85"
      />

      <!-- Ingredient-record trace path -->
      <path
        d="
          M88 1173
          C96 1166 96 1155 105 1148
          C114 1141 124 1145 130 1154
          C136 1164 131 1175 121 1180
        "
        fill="none"
        stroke="#F8F5EC"
        stroke-width="2"
        stroke-linecap="round"
        opacity="0.94"
      />

      <!-- Trace nodes -->
      <circle
        cx="88"
        cy="1173"
        r="3.4"
        fill="#F8F5EC"
      />

      <circle
        cx="105"
        cy="1148"
        r="3.4"
        fill="#F8F5EC"
      />

      <circle
        cx="130"
        cy="1154"
        r="4"
        fill="${accent}"
      />

      <circle
        cx="121"
        cy="1180"
        r="3.4"
        fill="#F8F5EC"
      />

      <!-- Small measured contribution mark -->
      <circle
        cx="112"
        cy="1162"
        r="7"
        fill="none"
        stroke="${accent}"
        stroke-width="1.5"
        opacity="0.82"
      />

      <circle
        cx="112"
        cy="1162"
        r="2.5"
        fill="${accent}"
      />

      <!-- Eyebrow label -->
      <text
        x="194"
        y="1147"
        font-family="Arial, sans-serif"
        font-size="11"
        font-weight="700"
        letter-spacing="2"
        fill="${accent}"
      >${microLabel}</text>

      <!-- Dynamic allergen result -->
      <text
        x="194"
        y="1172"
        font-family="Arial, sans-serif"
        font-size="22"
        font-weight="700"
        fill="#0B433D"
      >${escapeXml(
        truncateShareLabel(
          title,
          52
        )
      )}</text>

      <!-- Supporting safety note -->
      <text
        x="194"
        y="1191"
        font-family="Arial, sans-serif"
        font-size="14"
        font-weight="400"
        fill="#5D6C66"
      >Always check product labels if you have food allergies.</text>

      <!-- Subtle ingredient-label scan pattern -->
      <g
        opacity="0.25"
        stroke-linecap="round"
      >
        <line
          x1="866"
          y1="1144"
          x2="985"
          y2="1144"
          stroke="${accent}"
          stroke-width="1.5"
        />

        <line
          x1="891"
          y1="1154"
          x2="985"
          y2="1154"
          stroke="#8FA096"
          stroke-width="1.3"
        />

        <line
          x1="876"
          y1="1164"
          x2="985"
          y2="1164"
          stroke="#8FA096"
          stroke-width="1.3"
        />

        <line
          x1="907"
          y1="1174"
          x2="985"
          y2="1174"
          stroke="${accent}"
          stroke-width="1.3"
        />

        <line
          x1="884"
          y1="1184"
          x2="985"
          y2="1184"
          stroke="#8FA096"
          stroke-width="1.3"
        />

        <circle
          cx="875"
          cy="1144"
          r="3"
          fill="${accent}"
          stroke="none"
        />

        <circle
          cx="900"
          cy="1174"
          r="2.5"
          fill="${accent}"
          stroke="none"
        />
      </g>
    `;
  }

  function buildSvg(payload) {
    const data = payload || {};

    const name =
      safeText(data.name) ||
      'Your PureFyul Smoothie';

    const audience =
      safeText(data.audience) ||
      'General audience';

    const timing =
      safeText(data.timing) ||
      'Any time';

    const healthGoal =
      safeText(data.healthGoal) ||
      'No specific goal';

    const insight =
      safeText(data.insight) ||
      (
        'This result reflects the selected ' +
        'ingredient portions.'
      );

    const allergenTitle =
      normalizeAllergenTitle(
        data.allergen
      );

    const nutrition =
      data.nutrition || {};

    const ingredients =
      Array.isArray(data.ingredients)
        ? data.ingredients
        : [];

    const titleFontSize =
      name.length > 34
        ? 68
        : (
            name.length > 27
              ? 75
              : 83
          );

    const titleLines =
      buildEditorialTitleLines(
        name,
        titleFontSize
      );

    const titleLineHeight =
      titleFontSize + 5;

    const titleStartY =
      titleLines.length >= 3
        ? 278
        : (
            titleLines.length === 2
              ? 334
              : 396
          );

    const titleBottomY =
      titleStartY +
      (
        titleLines.length - 1
      ) * titleLineHeight;

    /*
     * Distinctive editorial title:
     * each line advances slightly, while only
     * the final line receives the warm accent.
     */
    const titleMarkup =
      titleLines
        .map((line, index) => {
          const isFinalLine =
            index === titleLines.length - 1;

          const useAccent =
            titleLines.length > 1 &&
            isFinalLine;

          const lineX =
            64 +
            Math.min(index, 2) * 24 +
            (
              useAccent
                ? 8
                : 0
            );

          const lineY =
            titleStartY +
            index * titleLineHeight;

          const lineSize =
            useAccent
              ? titleFontSize + 4
              : titleFontSize;

          const lineFill =
            useAccent
              ? '#B48C45'
              : BRAND_GREEN;

          const lineStyle =
            useAccent
              ? 'font-style="italic" '
              : '';

          return `
            <text
              x="${lineX}"
              y="${lineY}"
              font-family="
                'Bodoni 72',
                Didot,
                'Iowan Old Style',
                'Times New Roman',
                Georgia,
                serif
              "
              font-size="${lineSize}"
              font-weight="400"
              ${lineStyle}
              letter-spacing="-1.25"
              fill="${lineFill}"
            >${escapeXml(line)}</text>
          `;
        })
        .join('');

    const metadataLabelY =
      titleBottomY + 72;

    const metadataValueY =
      metadataLabelY + 29;

    const audienceDisplay =
      truncateShareLabel(
        audience,
        24
      );

    const timingDisplay =
      truncateShareLabel(
        timing,
        18
      );

    const healthGoalDisplay =
      truncateShareLabel(
        healthGoal,
        22
      );

    const insightLines =
      wrapText(
        insight,
        395,
        '400 25px Arial',
        5
      );

    return `
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="${CARD_WIDTH}"
        height="${CARD_HEIGHT}"
        viewBox="0 0 ${CARD_WIDTH} ${CARD_HEIGHT}"
      >
        <defs>
          <linearGradient
            id="pf-footer-gradient"
            x1="0"
            y1="0"
            x2="1"
            y2="0"
          >
            <stop
              offset="0%"
              stop-color="#053F38"
            />

            <stop
              offset="100%"
              stop-color="#07594E"
            />
          </linearGradient>
          <linearGradient
            id="pf-insight-surface"
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop
              offset="0%"
              stop-color="#F8F3EA"
            />

            <stop
              offset="48%"
              stop-color="#F0EFE5"
            />

            <stop
              offset="100%"
              stop-color="#E3E8D9"
            />
          </linearGradient>

          <radialGradient
            id="pf-insight-warm-glow"
            cx="0.12"
            cy="0.10"
            r="0.95"
          >
            <stop
              offset="0%"
              stop-color="#FFFDF8"
              stop-opacity="0.78"
            />

            <stop
              offset="58%"
              stop-color="#F8F2E8"
              stop-opacity="0.18"
            />

            <stop
              offset="100%"
              stop-color="#DDE4D4"
              stop-opacity="0"
            />
          </radialGradient>
          <linearGradient
            id="pf-insight-leaf-fill"
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop
              offset="0%"
              stop-color="#D4D8C8"
            />

            <stop
              offset="100%"
              stop-color="#C4CAB7"
            />
          </linearGradient>

          <linearGradient
            id="pf-insight-icon-bg"
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop
              offset="0%"
              stop-color="#164B48"
            />

            <stop
              offset="100%"
              stop-color="#0D3434"
            />
          </linearGradient>


          <clipPath id="pf-insight-clip">
            <rect
              x="64"
              y="874"
              width="524"
              height="230"
              rx="27"
            />
          </clipPath>


          <filter
            id="pf-soft-shadow"
            x="-20%"
            y="-20%"
            width="140%"
            height="150%"
          >
            <feDropShadow
              dx="0"
              dy="4"
              stdDeviation="7"
              flood-color="#17372F"
              flood-opacity="0.055"
            />
          </filter>
        </defs>

        <rect
          width="${CARD_WIDTH}"
          height="${CARD_HEIGHT}"
          fill="#FAF5EC"
        />

        ${buildPremiumBotanical(ingredients)}

        <!-- Refined PureFyul masthead -->
        <g
          transform="translate(64 43) scale(0.90)"
          fill="none"
          stroke="${BRAND_GREEN}"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path
            d="
              M25 48
              C7 39 4 18 10 4
              C28 10 38 28 25 48
              Z
            "
          />

          <path
            d="
              M29 48
              C47 39 52 18 47 4
              C29 10 18 29 29 48
              Z
            "
          />

          <path d="M27 47 V65"/>
        </g>

        <text
          x="120"
          y="92"
          font-family="
            'Bodoni 72',
            Didot,
            'Iowan Old Style',
            'Times New Roman',
            Georgia,
            serif
          "
          font-size="44"
          font-weight="400"
          letter-spacing="-0.5"
          fill="${BRAND_GREEN}"
        >PureFyul</text>

        <!-- Quiet masthead rule -->
        <line
          x1="64"
          y1="124"
          x2="352"
          y2="124"
          stroke="#B48C45"
          stroke-width="1.8"
          stroke-linecap="round"
          opacity="0.82"
        />

        <!-- Staggered editorial smoothie title -->
        ${titleMarkup}

        <!-- Editorial recipe credits -->
        <g>
          <text
            x="64"
            y="${metadataLabelY}"
            font-family="Arial, sans-serif"
            font-size="11.5"
            font-weight="700"
            letter-spacing="2.15"
            fill="#B48C45"
          >FOR</text>

          <text
            x="64"
            y="${metadataValueY}"
            font-family="Arial, sans-serif"
            font-size="20"
            font-weight="500"
            fill="#40524B"
          >${escapeXml(audienceDisplay)}</text>

          <text
            x="298"
            y="${metadataLabelY}"
            font-family="Arial, sans-serif"
            font-size="11.5"
            font-weight="700"
            letter-spacing="2.15"
            fill="#B48C45"
          >WHEN</text>

          <text
            x="298"
            y="${metadataValueY}"
            font-family="Arial, sans-serif"
            font-size="20"
            font-weight="500"
            fill="#40524B"
          >${escapeXml(timingDisplay)}</text>

          <text
            x="506"
            y="${metadataLabelY}"
            font-family="Arial, sans-serif"
            font-size="11.5"
            font-weight="700"
            letter-spacing="2.15"
            fill="#B48C45"
          >GOAL</text>

          <text
            x="506"
            y="${metadataValueY}"
            font-family="Arial, sans-serif"
            font-size="20"
            font-weight="500"
            fill="#40524B"
          >${escapeXml(healthGoalDisplay)}</text>
        </g>

        ${buildMetricCards(nutrition)}

        <!-- Premium Ingredient Insight surface -->
        <rect
          x="64"
          y="874"
          width="524"
          height="230"
          rx="27"
          fill="url(#pf-insight-surface)"
          stroke="#C8CDBD"
          stroke-width="1.2"
        />

        <!-- Warm ivory atmospheric highlight -->
        <rect
          x="65"
          y="875"
          width="522"
          height="228"
          rx="26"
          fill="url(#pf-insight-warm-glow)"
          clip-path="url(#pf-insight-clip)"
        />

        <!-- Very subtle upper edge highlight -->
        <path
          d="
            M91 875
            H558
          "
          fill="none"
          stroke="#FFFFFF"
          stroke-width="1.4"
          stroke-linecap="round"
          opacity="0.58"
        />

        <!-- Refined nutrition composition dial -->
        <g
          opacity="0.34"
          clip-path="url(#pf-insight-clip)"
        >
          <!-- Soft background wash -->
          <circle
            cx="558"
            cy="1027"
            r="62"
            fill="#DDE3D7"
            opacity="0.38"
          />

          <!-- Outer measurement ring -->
          <circle
            cx="558"
            cy="1027"
            r="51"
            fill="none"
            stroke="#AEB9A8"
            stroke-width="1.5"
          />

          <!-- Warm inner ring -->
          <circle
            cx="558"
            cy="1027"
            r="31"
            fill="none"
            stroke="#C4AA72"
            stroke-width="1.5"
          />

          <!-- Quiet composition axes -->
          <line
            x1="558"
            y1="976"
            x2="558"
            y2="987"
            stroke="#B7A36F"
            stroke-width="1.7"
            stroke-linecap="round"
          />

          <line
            x1="558"
            y1="1067"
            x2="558"
            y2="1078"
            stroke="#B7A36F"
            stroke-width="1.7"
            stroke-linecap="round"
          />

          <line
            x1="507"
            y1="1027"
            x2="518"
            y2="1027"
            stroke="#B7A36F"
            stroke-width="1.7"
            stroke-linecap="round"
          />

          <line
            x1="598"
            y1="1027"
            x2="609"
            y2="1027"
            stroke="#B7A36F"
            stroke-width="1.7"
            stroke-linecap="round"
          />

          <!-- Ingredient contribution paths -->
          <line
            x1="558"
            y1="1027"
            x2="535"
            y2="1003"
            stroke="#AEB9A8"
            stroke-width="1.8"
          />

          <line
            x1="558"
            y1="1027"
            x2="579"
            y2="1001"
            stroke="#AEB9A8"
            stroke-width="1.8"
          />

          <line
            x1="558"
            y1="1027"
            x2="582"
            y2="1050"
            stroke="#AEB9A8"
            stroke-width="1.8"
          />

          <!-- Contribution points -->
          <circle
            cx="535"
            cy="1003"
            r="6"
            fill="#C9D0C1"
          />

          <circle
            cx="579"
            cy="1001"
            r="6"
            fill="#C9B27E"
          />

          <circle
            cx="582"
            cy="1050"
            r="7"
            fill="#C9D0C1"
          />

          <!-- Main measured result -->
          <circle
            cx="558"
            cy="1027"
            r="10"
            fill="#0F766E"
            opacity="0.76"
          />

          <circle
            cx="558"
            cy="1027"
            r="3.5"
            fill="#FFFDF8"
          />
        </g>

        <!-- Premium composition-dial icon -->
        <circle
          cx="110"
          cy="922"
          r="23"
          fill="url(#pf-insight-icon-bg)"
        />

        <!-- Thin analytical ring -->
        <circle
          cx="110"
          cy="922"
          r="11"
          fill="none"
          stroke="#FFFFFF"
          stroke-width="1.6"
          opacity="0.94"
        />

        <!-- Three measured ingredient points -->
        <circle
          cx="105"
          cy="916"
          r="2.5"
          fill="#FFFFFF"
        />

        <circle
          cx="117"
          cy="918"
          r="2.5"
          fill="#FFFFFF"
        />

        <circle
          cx="108"
          cy="929"
          r="2.5"
          fill="#FFFFFF"
        />

        <!-- Fine composition lines -->
        <line
          x1="110"
          y1="922"
          x2="105"
          y2="916"
          stroke="#FFFFFF"
          stroke-width="1.4"
          stroke-linecap="round"
        />

        <line
          x1="110"
          y1="922"
          x2="117"
          y2="918"
          stroke="#FFFFFF"
          stroke-width="1.4"
          stroke-linecap="round"
        />

        <line
          x1="110"
          y1="922"
          x2="108"
          y2="929"
          stroke="#FFFFFF"
          stroke-width="1.4"
          stroke-linecap="round"
        />

        <!-- Warm focal point -->
        <circle
          cx="110"
          cy="922"
          r="3"
          fill="#D2B36F"
        />

        <!-- Heading -->
        <text
          x="148"
          y="929"
          font-family="Arial, sans-serif"
          font-size="18"
          font-weight="700"
          letter-spacing="1.8"
          fill="#0F766E"
        >INGREDIENT INSIGHT</text>

        <!-- Dynamic insight text -->
        ${svgTextLines(
          insightLines,
          100,
          980,
          34,
          (
            'font-family="Arial, sans-serif" ' +
            'font-size="25" font-weight="400" ' +
            'fill="#073F38"'
          )
        )}

        <!-- Premium Ingredients heading -->
        <text
          x="626"
          y="895"
          font-family="Arial, sans-serif"
          font-size="18"
          font-weight="700"
          letter-spacing="2.2"
          fill="#0F766E"
        >INGREDIENTS</text>

        <!-- Fine editorial continuation rule -->
        <line
          x1="780"
          y1="889"
          x2="1014"
          y2="889"
          stroke="#AEB9B2"
          stroke-width="1.4"
          stroke-linecap="round"
          opacity="0.88"
        />

        ${buildIngredientRows(ingredients)}

        ${buildAllergenStrip(allergenTitle)}

        <rect
          x="64"
          y="1217"
          width="952"
          height="119"
          rx="28"
          fill="url(#pf-footer-gradient)"
          filter="url(#pf-soft-shadow)"
        />

        <!-- Final PureFyul editorial CTA lockup -->
        <text
          x="102"
          y="1254"
          font-family="Arial, sans-serif"
          font-size="13"
          font-weight="700"
          letter-spacing="2.35"
          fill="#D2B66F"
        >BUILD YOUR OWN</text>

        <!-- Expressive editorial keyword -->
        <text
          x="102"
          y="1298"
          font-family="
            'Bodoni 72',
            Didot,
            'Iowan Old Style',
            'Times New Roman',
            Georgia,
            serif
          "
          font-size="40"
          font-weight="500"
          font-style="italic"
          letter-spacing="-0.8"
          fill="#FFFDF8"
        >free</text>

        <!-- Calm product descriptor -->
        <text
          x="175"
          y="1297"
          font-family="Arial, sans-serif"
          font-size="23"
          font-weight="600"
          letter-spacing="0.15"
          fill="#E7EEE9"
        >smoothie</text>

        <line
          x1="420"
          y1="1238"
          x2="420"
          y2="1315"
          stroke="#FFFFFF"
          stroke-opacity="0.28"
          stroke-width="2"
        />

        <!-- PureFyul culinary signature -->
        <g>
          <!-- Editorial wordmark -->
          <text
            x="472"
            y="1267"
            font-family="
              'Bodoni 72',
              Didot,
              'Iowan Old Style',
              'Times New Roman',
              Georgia,
              serif
            "
            font-size="36"
            font-weight="500"
            font-style="italic"
            letter-spacing="-0.5"
            fill="#FFFDF8"
          >PureFyul</text>

          <!-- Flowing blend ribbon -->
          <path
            d="
              M472 1279
              C520 1272 570 1284 616 1279
              C661 1274 696 1263 733 1269
            "
            fill="none"
            stroke="#D1B36D"
            stroke-width="2.4"
            stroke-linecap="round"
            opacity="0.96"
          />

          <!-- App destination -->
          <text
            x="472"
            y="1305"
            font-family="Arial, sans-serif"
            font-size="18"
            font-weight="600"
            letter-spacing="0.2"
            fill="#E3EDE8"
          >purefyul.com/app</text>
        </g>

        <line
          x1="804"
          y1="1238"
          x2="804"
          y2="1315"
          stroke="#FFFFFF"
          stroke-opacity="0.24"
          stroke-width="2"
        />

        <text
          x="929"
          y="1240"
          text-anchor="middle"
          font-family="Arial, sans-serif"
          font-size="13"
          font-weight="700"
          letter-spacing="1.3"
          fill="#E3EDE8"
        >SCAN TO BUILD</text>

        ${buildQrSvg(
          886,
          1247,
          84
        )}
      </svg>
    `;
  }

  function safeFileName(name) {
    const slug = safeText(name)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 48);

    return `${slug || 'purefyul-result'}.png`;
  }

  async function createPng(payload) {
    const svg = buildSvg(payload);
    const svgBlob = new Blob([svg], {
      type: 'image/svg+xml;charset=utf-8'
    });
    const svgUrl = URL.createObjectURL(svgBlob);

    try {
      const image = new Image();

      await new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = () => reject(new Error('Share card SVG could not be rendered.'));
        image.src = svgUrl;
      });

      const canvas = document.createElement('canvas');
      canvas.width = CARD_WIDTH;
      canvas.height = CARD_HEIGHT;

      const context = canvas.getContext('2d');
      context.fillStyle = CARD_BACKGROUND;
      context.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT);
      context.drawImage(image, 0, 0, CARD_WIDTH, CARD_HEIGHT);

      const blob = await new Promise((resolve, reject) => {
        canvas.toBlob(result => {
          if (!result) {
            reject(new Error('Share card PNG could not be created.'));
            return;
          }

          resolve(result);
        }, 'image/png', 0.95);
      });

      return blob;
    } finally {
      URL.revokeObjectURL(svgUrl);
    }
  }

  function downloadBlob(blob, fileName) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  let preparedCard = null;
  let preparationToken = 0;

  function getPayloadKey(payload) {
    return JSON.stringify(payload || {});
  }

  async function prepare(payload) {
    const token = ++preparationToken;
    const key = getPayloadKey(payload);
    const blob = await createPng(payload);

    // Ignore an older card if a newer smoothie/result
    // began preparing before this render completed.
    if (token !== preparationToken) {
      return {
        mode: 'stale'
      };
    }

    const fileName = safeFileName(payload?.name);
    const file = new File([blob], fileName, {
      type: 'image/png',
      lastModified: Date.now()
    });

    let canShareFile = false;

    try {
      canShareFile = Boolean(
        navigator.share &&
        navigator.canShare &&
        navigator.canShare({
          files: [file]
        })
      );
    } catch (error) {
      canShareFile = false;
    }

    preparedCard = {
      key,
      blob,
      file,
      fileName,
      canShareFile
    };

    return {
      mode: 'prepared',
      fileName,
      canShareFile
    };
  }

  function isPrepared(payload) {
    return Boolean(
      preparedCard &&
      preparedCard.key === getPayloadKey(payload)
    );
  }

  function clearPrepared() {
    preparationToken += 1;
    preparedCard = null;
  }

  async function download(payload) {
    const key = getPayloadKey(payload);

    if (
      preparedCard &&
      preparedCard.key === key
    ) {
      downloadBlob(
        preparedCard.blob,
        preparedCard.fileName
      );

      return {
        mode: 'download',
        fileName: preparedCard.fileName
      };
    }

    const blob = await createPng(payload);
    const fileName = safeFileName(payload?.name);

    downloadBlob(blob, fileName);

    return {
      mode: 'download',
      fileName
    };
  }

  function sharePrepared(payload) {
    const key = getPayloadKey(payload);

    if (
      !preparedCard ||
      preparedCard.key !== key
    ) {
      return Promise.reject(
        new Error(
          'PureFyul share card is not prepared yet.'
        )
      );
    }

    if (preparedCard.canShareFile) {
      // No asynchronous image-generation work happens
      // before navigator.share(). This preserves the
      // button-click user activation.
      return navigator.share({
        files: [preparedCard.file],
        title:
          safeText(payload?.name) ||
          'PureFyul smoothie result'
      }).then(() => ({
        mode: 'share',
        fileName: preparedCard.fileName
      }));
    }

    downloadBlob(
      preparedCard.blob,
      preparedCard.fileName
    );

    return Promise.resolve({
      mode: 'download',
      fileName: preparedCard.fileName
    });
  }

  function share(payload) {
    return sharePrepared(payload);
  }

  window.PureFyulShareCard = Object.freeze({
    buildSvg,
    clearPrepared,
    createPng,
    download,
    getSmoothieColors,
    isPrepared,
    prepare,
    share,
    sharePrepared,
    version: '7.9.8'
  });
})();
