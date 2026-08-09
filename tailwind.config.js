const path = require("path");
const { execSync } = require("child_process");

/**
 * LOCATE THE INSTALLED django_fundamentals PACKAGE.
 *
 * ITS TEMPLATES MUST BE SCANNED BY TAILWIND OR EVERY CLASS USED ONLY BY THE
 * PACKAGE'S OWN CHROME (SIDEBAR, NAVBAR, AUTH PAGES) GETS PURGED AND THE APP
 * RENDERS UNSTYLED.
 *
 * DO NOT HARD-CODE A PATH LIKE "./.venv/lib/**" — THE INSTALL DOCS USE CONDA,
 * WHERE site-packages LIVES OUTSIDE THE PROJECT ENTIRELY, AND THE ANSIBLE
 * DEPLOY ROLE USES /home/<user>/venv. ASKING PYTHON WHERE THE PACKAGE ACTUALLY
 * IS WORKS FOR ALL OF THEM, INCLUDING EDITABLE INSTALLS.
 */
function findDjangoFundamentals() {
    const python = process.env.PYTHON || "python";
    try {
        return execSync(
            `${python} -c "import django_fundamentals,os;print(os.path.dirname(django_fundamentals.__file__))"`,
            { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }
        ).trim();
    } catch (e) {
        // FAIL LOUDLY RATHER THAN WARN. FALLING BACK SILENTLY PRODUCES A
        // STYLESHEET THAT IS MISSING EVERY SEMANTIC CLASS THE PACKAGE USES, AND
        // A BUILD THAT "SUCCEEDS" WHILE THE APP RENDERS UNSTYLED IS FAR HARDER
        // TO DIAGNOSE THAN ONE THAT STOPS HERE.
        throw new Error(
            "\n\n  Tailwind could not import django_fundamentals using '" + python + "'.\n\n" +
            "  Its templates and design preset are required to build the stylesheet.\n" +
            "  Fix it by either:\n" +
            "    * activating your environment first  (conda activate <env>), or\n" +
            "    * pointing PYTHON at the right interpreter:\n" +
            "        PYTHON=/path/to/python npm run build:css\n\n" +
            "  Original error: " + e.message + "\n"
        );
    }
}

const packageDir = findDjangoFundamentals();

module.exports = {
    // THE SEMANTIC NAME -> CSS VARIABLE MAPPING LIVES IN THE PACKAGE SO IT
    // REACHES THIS PROJECT VIA `pip install -U django-fundamentals`. THE VALUES
    // IT POINTS AT ARE YOURS, IN static/src/tokens.css.
    presets: [
        require(path.join(packageDir, "static/django_fundamentals/tailwind-preset.js")),
    ],

    content: [
        "./templates/**/*.html",
        "./apps/**/templates/**/*.html",
        "./sherlog/**/*.py",
        path.join(packageDir, "templates/**/*.html"),
        // THE PACKAGE'S PYTHON TOO, NOT JUST ITS TEMPLATES: SOME CLASS STRINGS
        // ARE BUILT IN CODE RATHER THAN WRITTEN IN MARKUP (e.g. THE BUTTON
        // VARIANTS IN templatetags/django_fundamentals.py). MISSING THESE
        // SILENTLY DROPS bg-brand/text-brand-fg AND BUTTONS RENDER BARE.
        path.join(packageDir, "**/*.py"),
    ],

    // PROJECT-SPECIFIC OVERRIDES GO HERE. FOR COLOURS AND DIMENSIONS, PREFER
    // EDITING static/src/tokens.css — IT DRIVES BOTH LIGHT AND DARK THEMES.
    theme: {
        extend: {},
    },

    plugins: [],
};
