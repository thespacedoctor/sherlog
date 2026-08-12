/*
 * SKY VIEW — RENDER EVERY [data-sky-view] CONTAINER AS AN ALADIN LITE v3 VIEW.
 *
 * THE SURVEY IS CHOSEN PER POSITION: THE DEEPEST OPTICAL IMAGING THAT ACTUALLY
 * COVERS IT, DECIDED BY A SINGLE CONE QUERY AGAINST THE CDS MOCServer (THE SAME
 * REGISTRY ALADIN ITSELF USES). WITHOUT THAT CHECK A TRANSIENT OUTSIDE, SAY, THE
 * DESI FOOTPRINT WOULD RENDER AS AN EMPTY BLACK FRAME.
 *
 * ON TOP OF THE TRANSIENT'S OWN MARKER IT RINGS EVERY SOURCE SHERLOCK MATCHED,
 * EACH WITH THE RADIUS THAT FOUND IT, IN THE COLOUR ITS TABLE ROW CARRIES.
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
const ARCSEC_PER_DEG = 3600;
const MARKER_HALF_SIZE_DEG = 0.5 / ARCSEC_PER_DEG; // 0.5 ARCSEC, EACH ARM OF THE X
const MARKER_COLOUR = "red";
const MARKER_NAME = "transient";
// A POINT AT THE EXACT CENTRE OF EACH SOURCE CIRCLE, ON TOP OF ITS SEARCH RADIUS.
const CENTRE_DOT_RADIUS_DEG = 0.3 / ARCSEC_PER_DEG; // 0.3 ARCSEC

// ONE COLOUR PER RANK, MATCHING THE ROW COLOURS IN THE CROSSMATCH TABLE. THESE
// ARE THE DARK-THEME STEPS OF THE --color-rank-* TOKENS IN static/src/tokens.css
// AND MUST BE CHANGED ALONGSIDE THEM. THEY ARE HARD-CODED RATHER THAN READ FROM
// THE TOKENS BECAUSE ALADIN PAINTS ONTO A CANVAS: A COLOUR RESOLVED FROM CSS IS
// BAKED IN AT DRAW TIME AND WOULD NOT FOLLOW THE THEME TOGGLE. THE DARK STEPS
// ARE THE RIGHT ONES REGARDLESS — THESE CIRCLES ALWAYS SIT ON A SKY IMAGE.
const RANK_COLOURS = [
    "#3987e5", // 1 blue
    "#d95926", // 2 orange
    "#199e70", // 3 aqua
    "#c98500", // 4 yellow
    "#d55181", // 5 magenta
    "#008300", // 6 green
    "#9085e9", // 7 violet
    "#e66767", // 8 red
];
const RANK_OTHER_COLOUR = "#94a3b8"; // RANK 9 AND BEYOND SHARE ONE MUTED STEP

// CDS'S PROGRESSIVE CATALOGUE SERVICE — LEVEL-OF-DETAIL AWARE, SO THE CATALOGUES
// SERVED FROM HERE KEEP DRAWING HOWEVER FAR THE VIEW IS PANNED OR ZOOMED.
const HIPS_CAT_BASE = "https://hipscat.cds.unistra.fr/HiPSCatService";
// THE DESI LEGACY SURVEYS HAVE NO CATALOGUE HiPS AT CDS — ONLY THE IMAGERY, WHICH
// IS ALREADY THE FIRST ENTRY IN SURVEY_CHAIN. THE SOURCES COME FROM NOIRLab'S CONE
// SEARCH INSTEAD, WHICH SENDS NO CORS HEADERS AND SO HAS TO GO THROUGH ALADIN'S
// PROXY — SEE THE useProxy ARGUMENT IN THE BUILDER BELOW.
const DESI_DR10_SCS_URL = "https://datalab.noirlab.edu/scs/ls_dr10/tractor";
// CONE RADIUS FOR THE CATALOGUES FETCHED ONCE RATHER THAN PROGRESSIVELY, IN
// DEGREES. WIDER THAN FIELD_OF_VIEW_DEG SO A SMALL PAN STILL HAS SOURCES IN IT.
const CATALOGUE_CONE_RADIUS_DEG = 0.05;
// DESI GETS A TIGHTER CONE THAN THE REST BECAUSE ITS CONE SEARCH RETURNS EVERY
// TRACTOR COLUMN — ABOUT 150 OF THEM — SO EACH SOURCE COSTS ~3.4 kB. AT 0.05 deg
// THAT IS A 4.6 MB RESPONSE; AT 0.025 deg IT IS 0.5 MB, WHICH STILL COMFORTABLY
// COVERS THE DEFAULT FIELD OF VIEW.
const DESI_CONE_RADIUS_DEG = 0.025;
// ALADIN DRAWS EACH MARKER ONTO A CANVAS THIS MANY PIXELS SQUARE WITH A 2px
// STROKE, SO AT ITS DEFAULT OF 8 A RHOMB AND A CIRCLE ARE THE SAME LITTLE RING.
// 12 IS THE POINT AT WHICH THE SHAPES READ AS THEMSELVES.
const CATALOGUE_SOURCE_SIZE = 12;

const OVERLAY_DATA_ID = "sky-view-crossmatches";
// hide | top | merged | all — WHAT THE PILL OVER THE VIEW SWITCHES BETWEEN.
const DEFAULT_MODE = "top";
// THE SOURCE'S OWN EXTENT IS DRAWN DASHED AND THINNER THAN ITS SEARCH RADIUS.
// lineDash IS AN OVERLAY OPTION, NOT A PER-SHAPE ONE, WHICH IS WHY EACH RANK
// NEEDS A SECOND OVERLAY RATHER THAN A SECOND CIRCLE IN THE FIRST.
const EXTENT_LINE_DASH = [5, 5];
const SELECTION_LINE_WIDTH = 4;

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
 * THE CIRCLES DJANGO EMITTED FOR THIS PAGE, OR AN EMPTY LIST IF THERE ARE NONE.
 */
function readCrossmatches() {
    const block = document.getElementById(OVERLAY_DATA_ID);
    if (!block) {
        return [];
    }
    try {
        return JSON.parse(block.textContent) || [];
    } catch (error) {
        console.warn("[sky_view] could not read the crossmatch overlays", error);
        return [];
    }
}

/**
 * THE COLOUR FOR A RANK, GIVEN THE TOKEN SUFFIX THE SERVER CHOSE ("1".."8" OR
 * "other") — THE SAME MAPPING SherlockCrossmatch.rank_colour_token APPLIES.
 */
function colourForToken(token) {
    const slot = Number.parseInt(token, 10);
    return Number.isInteger(slot) && RANK_COLOURS[slot - 1] ? RANK_COLOURS[slot - 1] : RANK_OTHER_COLOUR;
}

/**
 * RING EVERY MATCHED SOURCE, TWO ALADIN OVERLAYS PER RANK SO THE LAYERS CONTROL
 * LISTS THEM SEPARATELY: THE SOLID SEARCH RADIUS THAT FOUND THE SOURCE, AND —
 * WHERE THE CATALOGUE GIVES ONE — A DASHED CIRCLE FOR THE SOURCE'S OWN EXTENT.
 *
 * EACH SEARCH OVERLAY HOLDS BOTH THE RANK'S LEAD CIRCLE AND THE CIRCLES OF THE
 * INDIVIDUAL CATALOGUE MATCHES MERGED INTO IT; SWITCHING MODE SHOWS AND HIDES
 * THE SHAPES RATHER THAN REBUILDING THE OVERLAYS.
 *
 * RETURNS A CONTROLLER, OR null WHEN THERE IS NOTHING TO DRAW.
 */
function drawCrossmatches(aladin, records) {
    if (!records.length) {
        return null;
    }

    const byRank = new Map();
    for (const record of records) {
        if (!byRank.has(record.rank)) {
            byRank.set(record.rank, []);
        }
        byRank.get(record.rank).push(record);
    }

    const groups = new Map();
    for (const rank of [...byRank.keys()].sort((left, right) => left - right)) {
        const rankRecords = byRank.get(rank);
        const colour = colourForToken(rankRecords[0].colourToken);

        const overlay = A.graphicOverlay({ name: `rank ${rank}`, color: colour, lineWidth: 2 });
        // ADDING THE OVERLAY FIRST IS NOT OPTIONAL: GraphicOverlay.add() REACHES
        // FOR this.view, WHICH ONLY EXISTS ONCE ALADIN OWNS THE OVERLAY.
        aladin.addOverlay(overlay);

        const leadCircles = [];
        const childCircles = [];
        const extents = [];
        for (const record of rankRecords) {
            const circle = A.circle(record.ra, record.dec, record.radiusArcsec / ARCSEC_PER_DEG, { color: colour });
            // STASHED SO A CLICK ON THE CANVAS CAN NAME THE ROW IT BELONGS TO.
            circle.sherlogRank = rank;
            overlay.add(circle);

            // A FILLED DOT AT THE EXACT CENTRE, ON THE SAME OVERLAY AS ITS SEARCH
            // RADIUS CIRCLE SO IT SHOWS/HIDES ALONGSIDE IT WITHOUT ANY EXTRA MODE
            // OR SELECTION HANDLING.
            const centreDot = A.circle(record.ra, record.dec, CENTRE_DOT_RADIUS_DEG, {
                color: colour,
                fillColor: colour,
            });
            centreDot.sherlogRank = rank;
            overlay.add(centreDot);

            const bucket = record.isLead ? leadCircles : childCircles;
            bucket.push(circle, centreDot);
            if (record.smAxisArcsec) {
                extents.push(record);
            }
        }

        // THE DASHES HAVE TO LIVE ON THEIR OWN OVERLAY — lineDash IS SET PER
        // OVERLAY, NOT PER SHAPE.
        let extentOverlay = null;
        if (extents.length) {
            extentOverlay = A.graphicOverlay({
                name: `rank ${rank} (extent)`,
                color: colour,
                lineWidth: 1,
                lineDash: EXTENT_LINE_DASH,
            });
            aladin.addOverlay(extentOverlay);
            for (const record of extents) {
                const circle = A.circle(record.ra, record.dec, record.smAxisArcsec / ARCSEC_PER_DEG, { color: colour });
                circle.sherlogRank = rank;
                extentOverlay.add(circle);
            }
        }

        groups.set(rank, {
            rank,
            colour,
            overlay,
            extentOverlay,
            lead: leadCircles,
            // A RANK THAT MERGED NOTHING HAS ONLY ITS LEAD, SO THAT ONE CIRCLE
            // STANDS FOR IT IN BOTH MODES.
            all: childCircles.length ? childCircles : leadCircles,
            leadRecord: rankRecords.find((record) => record.isLead) || rankRecords[0],
        });
    }

    labelRanks(aladin, groups);

    // ONE OVERLAY, CLEARED AND REDRAWN, RATHER THAN RESTYLING A CIRCLE IN PLACE:
    // A SHAPE'S lineWidth CANNOT BE CHANGED AFTER CONSTRUCTION IN A WAY THAT IS
    // GUARANTEED TO REDRAW.
    const selection = A.graphicOverlay({ name: "selected", color: "#ffffff", lineWidth: SELECTION_LINE_WIDTH });
    aladin.addOverlay(selection);

    let mode = DEFAULT_MODE;
    let selectedRank = null;

    // WHICH OF A GROUP'S CIRCLES forMode SHOWS, WITH NO SELECTION IN PLAY. "top"
    // BEHAVES LIKE "merged" (LEAD CIRCLES ONLY) BUT RESTRICTED TO RANK 1.
    function visibleCirclesFor(group, forMode) {
        if (forMode === "hide" || (forMode === "top" && group.rank !== 1)) {
            return [];
        }
        return forMode === "all" ? group.all : group.lead;
    }

    // THE PILL'S OWN VIEW, WITH NOTHING ISOLATED. USED BOTH WHEN THE PILL CHANGES
    // AND WHEN A SELECTION IS CLEARED, SO THE TWO NEVER DRIFT APART.
    function applyModeDisplay(forMode) {
        for (const group of groups.values()) {
            const visible = new Set(visibleCirclesFor(group, forMode));
            for (const circle of group.overlay.overlayItems) {
                if (visible.has(circle)) {
                    circle.show();
                } else {
                    circle.hide();
                }
            }
            group.overlay.reportChange();

            if (group.extentOverlay) {
                if (visible.size) {
                    group.extentOverlay.show();
                } else {
                    group.extentOverlay.hide();
                }
            }
        }
    }

    function setMode(nextMode) {
        mode = nextMode;
        selectedRank = null;
        selection.removeAll();
        selection.reportChange();
        applyModeDisplay(mode);
    }

    // SHOW ONLY rank's GROUP, HIDING EVERY OTHER — A SOURCE THE CURRENT MODE IS
    // HIDING (E.G. RANK 2 WHILE "Top match" IS ACTIVE) STILL APPEARS IF ITS ROW
    // OR CIRCLE IS CLICKED DIRECTLY.
    function isolate(rank) {
        for (const [groupRank, group] of groups) {
            const visible = new Set(groupRank === rank ? (mode === "all" ? group.all : group.lead) : []);
            for (const circle of group.overlay.overlayItems) {
                if (visible.has(circle)) {
                    circle.show();
                } else {
                    circle.hide();
                }
            }
            group.overlay.reportChange();
            if (group.extentOverlay) {
                if (groupRank === rank) {
                    group.extentOverlay.show();
                } else {
                    group.extentOverlay.hide();
                }
            }
        }
    }

    function select(rank) {
        if (mode === "hide") {
            return;
        }
        selection.removeAll();
        const group = rank === null || rank === selectedRank ? null : groups.get(rank);
        if (group) {
            selectedRank = rank;
            isolate(rank);
            const record = group.leadRecord;
            selection.add(
                A.circle(record.ra, record.dec, record.radiusArcsec / ARCSEC_PER_DEG, {
                    color: group.colour,
                    lineWidth: SELECTION_LINE_WIDTH,
                })
            );
        } else {
            // NO RANK, THE SAME RANK CLICKED AGAIN, OR AN UNKNOWN RANK — ALL
            // RESTORE THE PILL'S NORMAL, UN-ISOLATED VIEW.
            selectedRank = null;
            applyModeDisplay(mode);
        }
        selection.reportChange();
    }

    return { setMode, select, ranks: [...groups.keys()] };
}

/**
 * PUT A SMALL RANK NUMBER AT THE CENTRE OF EACH RANKED SOURCE.
 *
 * GRAPHIC OVERLAYS CANNOT CARRY TEXT, SO THE LABELS RIDE ON A CATALOGUE LAYER —
 * ONE PER RANK, SO EACH CAN TAKE THE RANK'S OWN COLOUR. WRAPPED BECAUSE THIS IS
 * THE ONE PIECE LEANING ON AN ALADIN FEATURE WE HAVE NOT SEEN RUN: IF IT IS
 * UNAVAILABLE THE CIRCLES MUST STILL DRAW.
 */
function labelRanks(aladin, groups) {
    try {
        for (const group of groups.values()) {
            const catalogue = A.catalog({
                name: `rank ${group.rank} (label)`,
                sourceSize: 1,
                shape: "circle",
                color: group.colour,
                displayLabel: true,
                labelColumn: "rank",
                labelColor: group.colour,
                labelFont: "10px sans-serif",
            });
            aladin.addCatalog(catalogue);
            catalogue.addSources([
                A.source(group.leadRecord.ra, group.leadRecord.dec, { rank: String(group.rank) }),
            ]);
        }
    } catch (error) {
        console.warn("[sky_view] could not label the ranks", error);
    }
}

/**
 * MARK THE TRANSIENT'S OWN POSITION WITH A SMALL RED X, BUILT FROM TWO CROSSING
 * LINES RATHER THAN AN ALADIN MARKER/ICON SO IT SCALES WITH THE SKY THE SAME WAY
 * THE SOURCE CIRCLES DO. THE RA HALF-WIDTH IS SCALED BY 1/cos(dec) SO THE X ISN'T
 * VISUALLY STRETCHED AWAY FROM THE EQUATOR.
 */
function drawTransientMarker(aladin, ra, decl) {
    const overlay = A.graphicOverlay({ name: MARKER_NAME, color: MARKER_COLOUR, lineWidth: 2 });
    aladin.addOverlay(overlay);

    const raHalf = MARKER_HALF_SIZE_DEG / Math.cos((decl * Math.PI) / 180);
    const decHalf = MARKER_HALF_SIZE_DEG;
    overlay.add(
        A.polyline([
            [ra - raHalf, decl - decHalf],
            [ra + raHalf, decl + decHalf],
        ])
    );
    overlay.add(
        A.polyline([
            [ra - raHalf, decl + decHalf],
            [ra + raHalf, decl - decHalf],
        ])
    );
}

/**
 * WIRE THE hide/top/merged/all SEGMENTED CONTROL SITTING OVER THE SKY VIEW.
 */
function wireModeToggle(container, setMode) {
    const modes = container.querySelector("[data-sky-view-modes]");
    if (!modes) {
        return;
    }
    // NOTHING TO CHOOSE BETWEEN UNTIL THERE ARE CIRCLES.
    modes.hidden = false;

    const buttons = [...modes.querySelectorAll("[data-sky-view-mode]")];
    for (const button of buttons) {
        button.addEventListener("click", () => {
            const mode = button.dataset.skyViewMode;
            for (const other of buttons) {
                other.setAttribute("aria-pressed", String(other === button));
            }
            setMode(mode);
        });
    }
}

/**
 * TIE THE CIRCLES AND THE CROSSMATCH TABLE TOGETHER: CLICKING EITHER HIGHLIGHTS
 * THE OTHER, SO A SOURCE ON THE SKY AND ITS ROW OF NUMBERS ARE OBVIOUSLY ONE
 * THING.
 */
function wireSelection(aladin, sky) {
    const rows = new Map();
    for (const group of document.querySelectorAll("[data-rank-group]")) {
        rows.set(Number.parseInt(group.dataset.rankGroup, 10), group);
    }

    function highlight(rank) {
        for (const [groupRank, element] of rows) {
            element.classList.toggle("rank-group-selected", groupRank === rank);
        }
    }

    for (const [rank, element] of rows) {
        element.addEventListener("click", (event) => {
            // THE EXPANDER BUTTON AND ANY LINK IN THE ROW KEEP THEIR OWN JOBS.
            if (event.target.closest("button, a")) {
                return;
            }
            const alreadyOn = element.classList.contains("rank-group-selected");
            highlight(alreadyOn ? null : rank);
            sky.select(alreadyOn ? null : rank);
        });
    }

    aladin.on("footprintClicked", (footprint) => {
        const rank = footprint && footprint.sherlogRank;
        if (rank === undefined) {
            return;
        }
        highlight(rank);
        sky.select(rank);
    });
}

/**
 * HOW TO FETCH EACH REFERENCE CATALOGUE THE TEMPLATE OFFERS, KEYED BY THE id IN
 * ITS data-sky-view-catalogue ATTRIBUTE. THE TEMPLATE OWNS THE LIST, THE NAMES
 * AND THE COLOURS; THIS ONLY KNOWS WHERE THE SOURCES COME FROM.
 *
 * EVERY BUILDER RETURNS ITS CATALOGUE SYNCHRONOUSLY AND FILLS IT IN LATER, SO
 * THE OBJECT CAN BE HANDED TO aladin.addCatalog() STRAIGHT AWAY. `progressive`
 * MARKS THE TWO THAT STREAM BY LEVEL OF DETAIL AND SO NEVER "FINISH" LOADING —
 * THE OTHER THREE ARE ONE-SHOT CONE SEARCHES THAT REPORT BACK THROUGH THEIR
 * SUCCESS/ERROR CALLBACKS.
 */
const CATALOGUE_BUILDERS = {
    "desi-dr10": {
        progressive: false,
        build: (ra, decl, options, onLoad, onFail) => {
            const url = `${DESI_DR10_SCS_URL}?RA=${ra}&DEC=${decl}&SR=${DESI_CONE_RADIUS_DEG}`;
            // THE LAST ARGUMENT IS useProxy. NOIRLab SENDS NO CORS HEADERS, SO
            // WITHOUT IT THE BROWSER BLOCKS THE REQUEST; PASSING IT EXPLICITLY
            // ALSO SKIPS THE DIRECT ATTEMPT ALADIN WOULD OTHERWISE MAKE FIRST.
            return A.catalogFromURL(url, options, onLoad, onFail, true);
        },
    },
    "gaia-dr3": {
        progressive: true,
        build: (ra, decl, options) => A.catalogHiPS(`${HIPS_CAT_BASE}/I/355/gaiadr3`, options),
    },
    "sdss-dr12": {
        // CDS'S PROGRESSIVE CATALOGUE SERVICE STOPS AT DR12 — THERE IS NO DR16 OR
        // LATER HiPS TO POINT AT, WHICH IS WHY THE LABEL SAYS DR12.
        progressive: true,
        build: (ra, decl, options) => A.catalogHiPS(`${HIPS_CAT_BASE}/V/147/sdss12`, options),
    },
    simbad: {
        progressive: false,
        build: (ra, decl, options, onLoad, onFail) =>
            A.catalogFromSimbad(`${ra} ${decl}`, CATALOGUE_CONE_RADIUS_DEG, options, onLoad, onFail),
    },
    ned: {
        progressive: false,
        build: (ra, decl, options, onLoad, onFail) =>
            A.catalogFromNED(`${ra} ${decl}`, CATALOGUE_CONE_RADIUS_DEG, options, onLoad, onFail),
    },
};

// A SHAPE PER CATALOGUE AS WELL AS A COLOUR: THE RANK CIRCLES ALREADY SPAN MOST
// OF THE HUES, SO SHAPE IS WHAT KEEPS TWO OVERLAYS APART WHEN THEY SIT CLOSE.
const CATALOGUE_SHAPES = {
    "desi-dr10": "square",
    "gaia-dr3": "circle",
    "sdss-dr12": "triangle",
    simbad: "rhomb",
    ned: "plus",
};

/**
 * WIRE THE REFERENCE-CATALOGUE CHECKBOXES ABOVE THE SKY VIEW.
 *
 * NOTHING IS FETCHED UNTIL A BOX IS FIRST TICKED — THREE OF THE FIVE ARE CONE
 * SEARCHES AND DESI ALONE IS HALF A MEGABYTE — AFTER WHICH THE CATALOGUE IS KEPT
 * AND MERELY SHOWN OR HIDDEN, SO TOGGLING IT AGAIN COSTS NOTHING.
 */
function wireCatalogues(container, aladin, ra, decl) {
    const list = document.querySelector("[data-sky-view-catalogues]");
    if (!list) {
        return;
    }
    // NOTHING TO TICK UNTIL THERE IS A VIEW TO DRAW INTO.
    list.hidden = false;

    // id -> CATALOGUE, ONCE BUILT. AN id PRESENT WITH A null VALUE IS IN FLIGHT:
    // A FAST DOUBLE-CLICK MUST NOT START A SECOND FETCH.
    const loaded = new Map();

    for (const input of list.querySelectorAll("[data-sky-view-catalogue]")) {
        const id = input.dataset.skyViewCatalogue;
        const entry = CATALOGUE_BUILDERS[id];
        const label = input.closest("label");
        const state = label.querySelector("[data-sky-view-catalogue-state]");
        // WHAT THE LAYERS CONTROL WILL CALL THIS CATALOGUE. READ NOW, WHILE THE
        // STATE SPAN IS STILL EMPTY, SO "loading…" NEVER LANDS IN THE NAME.
        const name = label.textContent.trim();

        if (!entry) {
            console.warn(`[sky_view] no builder for the "${id}" catalogue`);
            input.disabled = true;
            continue;
        }

        function say(message) {
            if (!state) {
                return;
            }
            state.textContent = message;
            state.hidden = !message;
        }

        input.addEventListener("change", () => {
            if (loaded.has(id)) {
                const catalogue = loaded.get(id);
                // STILL IN FLIGHT — THE change THAT STARTED IT WILL SHOW IT.
                if (catalogue) {
                    if (input.checked) {
                        catalogue.show();
                    } else {
                        catalogue.hide();
                    }
                }
                return;
            }
            if (!input.checked) {
                return;
            }

            loaded.set(id, null);
            say("loading…");

            function settle(catalogue) {
                loaded.set(id, catalogue);
                say("");
                // THE BOX MAY HAVE BEEN UNTICKED WHILE THE REQUEST WAS IN FLIGHT.
                if (!input.checked) {
                    catalogue.hide();
                }
            }

            function fail(error) {
                console.warn(`[sky_view] could not load the "${id}" catalogue`, error);
                // DROPPED FROM THE CACHE SO TICKING THE BOX AGAIN RETRIES.
                loaded.delete(id);
                input.checked = false;
                say("unavailable");
            }

            const options = {
                name,
                color: input.dataset.colour,
                shape: CATALOGUE_SHAPES[id],
                sourceSize: CATALOGUE_SOURCE_SIZE,
                onClick: "showTable",
            };

            let catalogue;
            try {
                catalogue = entry.build(ra, decl, options, settle, fail);
                aladin.addCatalog(catalogue);
            } catch (error) {
                fail(error);
                return;
            }

            // A PROGRESSIVE CATALOGUE HAS NO "LOADED" MOMENT TO WAIT FOR: IT KEEPS
            // FETCHING AS THE VIEW MOVES, SO IT IS SETTLED THE INSTANT IT EXISTS.
            if (entry.progressive) {
                settle(catalogue);
            }
        });
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
        // THE FRAME AND PROJECTION PICKERS ARE NOISE HERE — THE VIEW IS ALWAYS
        // ICRS/SIN. showCooLocation ALSO TAKES THE SEARCH BOX WITH IT: IN v3 THE
        // COORDINATE READOUT *IS* THE SEARCH FIELD, ONE WIDGET, NOT TWO.
        showFrame: false,
        showProjectionControl: false,
        showCooLocation: false,
        // ANCHORS THE STACK BUTTON TOP-RIGHT *AND* MAKES ITS MENU OPEN LEFTWARDS
        // — Toolbar.add() SETS openDirection FROM THIS. WITHOUT IT THE MENU
        // OPENS RIGHT AND FALLS OFF THE EDGE OF THE VIEW.
        toolbar: { position: "topright", vertical: true },
    });

    drawTransientMarker(aladin, ra, decl);

    const sky = drawCrossmatches(aladin, readCrossmatches());
    if (sky) {
        sky.setMode(DEFAULT_MODE);
        wireModeToggle(container, sky.setMode);
        wireSelection(aladin, sky);
        // THE LEGEND ONLY MAKES SENSE ONCE THERE ARE CIRCLES TO KEY.
        const legend = document.querySelector("[data-sky-view-legend]");
        if (legend) {
            legend.hidden = false;
        }
    }

    // UNLIKE THE LEGEND THIS IS NOT CONDITIONAL ON THERE BEING CIRCLES: THE
    // REFERENCE CATALOGUES ARE WORTH A LOOK PRECISELY WHEN SHERLOCK MATCHED
    // NOTHING.
    wireCatalogues(container, aladin, ra, decl);

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
    document.querySelectorAll("[data-sky-view]").forEach((container) => renderSkyView(container));
});
