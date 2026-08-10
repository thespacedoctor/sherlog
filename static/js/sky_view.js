/*
 * SKY VIEW — RENDER EVERY [data-sky-view] CONTAINER AS AN ALADIN LITE v3 VIEW.
 *
 * THE SURVEY IS CHOSEN PER POSITION: THE DEEPEST OPTICAL IMAGING THAT ACTUALLY
 * COVERS IT, DECIDED BY A SINGLE CONE QUERY AGAINST THE CDS MOCServer (THE SAME
 * REGISTRY ALADIN ITSELF USES). WITHOUT THAT CHECK A TRANSIENT OUTSIDE, SAY, THE
 * DESI FOOTPRINT WOULD RENDER AS AN EMPTY BLACK FRAME.
 */

// SURVEYS IN ORDER OF PREFERENCE. THE FIRST ONE COVERING THE POSITION WINS.
const SURVEY_CHAIN = [
    { id: "CDS/P/DESI-Legacy-Surveys/DR10/color", label: "DESI Legacy Surveys DR10" },
    { id: "CDS/P/PanSTARRS/DR1/color-i-r-g", label: "Pan-STARRS DR1" },
    { id: "CDS/P/SDSS9/color", label: "SDSS9" },
];
// ALL-SKY OPTICAL BACKSTOP, USED WHEN NOTHING ABOVE COVERS THE POSITION AND
// WHENEVER THE COVERAGE QUERY ITSELF FAILS.
const FALLBACK_SURVEY = { id: "CDS/P/DSS2/color", label: "DSS2" };

const MOCSERVER_URL = "https://alasky.cds.unistra.fr/MocServer/query";
// THE COVERAGE QUERY SITS BETWEEN THE PAGE AND THE FIRST TILE, SO IT IS GIVEN A
// SHORT LEASH — FALLING BACK TO DSS2 BEATS A SPINNER.
const MOCSERVER_TIMEOUT_MS = 2000;
// CONE RADIUS FOR THE COVERAGE QUERY, IN DEGREES. SMALL ENOUGH TO MEAN "THIS
// EXACT POSITION", LARGE ENOUGH TO SURVIVE MOC EDGE EFFECTS.
const COVERAGE_RADIUS_DEG = 0.001;

const FIELD_OF_VIEW_DEG = 0.033; // 2 ARCMIN — THE HOST GALAXY PLUS SOME CONTEXT
const MARKER_RADIUS_DEG = 0.00139; // 5 ARCSEC
const MARKER_COLOUR = "red";

// COALESCE THE STREAM OF SIZES A DRAG-RESIZE PRODUCES INTO ONE RE-FIT.
const RESIZE_DEBOUNCE_MS = 150;

/**
 * ASK THE MOCServer WHICH OF SURVEY_CHAIN COVER A POSITION, AND RETURN THE
 * FIRST BY PREFERENCE. FALLS BACK TO FALLBACK_SURVEY ON ANY FAILURE.
 */
async function chooseSurvey(ra, decl) {
    const url = new URL(MOCSERVER_URL);
    url.search = new URLSearchParams({
        RA: ra,
        DEC: decl,
        SR: COVERAGE_RADIUS_DEG,
        intersect: "enclosed",
        get: "id",
        fmt: "ascii",
        ID: SURVEY_CHAIN.map((survey) => survey.id).join(","),
    }).toString();

    try {
        const response = await fetch(url, { signal: AbortSignal.timeout(MOCSERVER_TIMEOUT_MS) });
        if (!response.ok) {
            throw new Error(`MOCServer returned ${response.status}`);
        }
        const covering = new Set(
            (await response.text())
                .split("\n")
                .map((line) => line.trim())
                .filter(Boolean)
        );
        return SURVEY_CHAIN.find((survey) => covering.has(survey.id)) || FALLBACK_SURVEY;
    } catch (error) {
        console.warn("[sky_view] coverage lookup failed, falling back to " + FALLBACK_SURVEY.id, error);
        return FALLBACK_SURVEY;
    }
}

/**
 * BUILD ONE ALADIN VIEW INSIDE `container`, CENTRED ON ITS data-ra/data-decl.
 */
async function renderSkyView(container) {
    const status = container.querySelector("[data-sky-view-status]");
    const ra = Number.parseFloat(container.dataset.ra);
    const decl = Number.parseFloat(container.dataset.decl);

    if (!Number.isFinite(ra) || !Number.isFinite(decl)) {
        if (status) status.textContent = "No sky position to display.";
        return;
    }

    const survey = await chooseSurvey(ra, decl);

    await A.init;

    // ALADIN APPENDS ITS OWN CHILDREN, SO THE PLACEHOLDER GOES FIRST.
    if (status) status.remove();

    const aladin = A.aladin(container, {
        survey: survey.id,
        target: `${ra} ${decl}`,
        fov: FIELD_OF_VIEW_DEG,
        projection: "SIN",
        cooFrame: "ICRS",
        showReticle: false,
        showCooGrid: false,
        showLayersControl: true,
        showFullscreenControl: true,
    });

    // OPEN CIRCLE — A graphicOverlay FOOTPRINT IS STROKED, NEVER FILLED, SO THE
    // SOURCE UNDERNEATH STAYS VISIBLE.
    const overlay = A.graphicOverlay({ color: MARKER_COLOUR, lineWidth: 2 });
    aladin.addOverlay(overlay);
    overlay.add(A.circle(ra, decl, MARKER_RADIUS_DEG));

    keepCanvasFitted(container, aladin);

    container.dataset.skyViewSurvey = survey.id;
}

/**
 * RE-FIT THE CANVAS WHEN THE CONTAINER CHANGES SIZE.
 *
 * ALADIN SIZES ITS CANVAS ONCE, AT INIT. THE CONTAINER'S HEIGHT IS A clamp()
 * AGAINST THE VIEWPORT AND ITS WIDTH FOLLOWS THE CONTENT COLUMN, SO WITHOUT
 * THIS A WINDOW RESIZE LEAVES THE OLD CANVAS STRETCHED INSIDE THE NEW BOX.
 * NEITHER A window RESIZE EVENT NOR A BARE STYLE CHANGE TRIGGERS IT ON ITS OWN,
 * WHICH IS WHY THIS WATCHES THE ELEMENT RATHER THAN THE WINDOW.
 */
function keepCanvasFitted(container, aladin) {
    if (typeof ResizeObserver === "undefined") {
        return;
    }
    let pending = null;
    const observer = new ResizeObserver(() => {
        window.clearTimeout(pending);
        pending = window.setTimeout(() => {
            // `view` IS NOT POPULATED THE INSTANT A.aladin() RETURNS, SO IT IS
            // CHECKED HERE RATHER THAN WHEN THE OBSERVER IS ATTACHED.
            if (aladin.view) {
                aladin.view.fixLayoutDimensions();
            }
        }, RESIZE_DEBOUNCE_MS);
    });
    observer.observe(container);
}

document.addEventListener("DOMContentLoaded", () => {
    if (typeof A === "undefined") {
        console.error("[sky_view] Aladin Lite failed to load");
        document.querySelectorAll("[data-sky-view-status]").forEach((status) => {
            status.textContent = "Sky image unavailable — Aladin Lite could not be loaded.";
        });
        return;
    }
    document.querySelectorAll("[data-sky-view]").forEach(renderSkyView);
});
