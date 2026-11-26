
/* ==================================================
   GSU GAS STATION DASHBOARD
   Interactive Google Maps Component

   Responsibilities:
   - Load Google Maps
   - Initialize and preserve the map
   - Manage station markers
   - Update radius circle continuously
   - Identify cheapest eligible stations
   - Display station information
   - Communicate selected radius to Streamlit
   ================================================== */


// Streamlit Components V2 entry point
export default function (component) {

    const {
        data,
        parentElement,
        setStateValue
    } = component;


    // ==================================================
    // 1. CONSTANTS
    // ==================================================

    const MILES_TO_METERS = 1609.344;

    const MIN_RADIUS = 0.50;
    const MAX_RADIUS = 3.00;

    const COLORS = {
        best: "#16a34a",
        cheapest: "#0d9488",
        eligible: "#2563eb",
        unavailable: "#94a3b8",
        campus: "#d97706",
        radius: "#2563eb"
    };


    // ==================================================
    // 2. PRESERVE MAP STATE
    // ==================================================

    // This state belongs to the component's DOM element.
    // It remains available across Streamlit reruns as long
    // as the component stays mounted with the same key.

    const state = parentElement._gsuMapState ??= {

        map: null,

        circle: null,

        infoWindow: null,

        markers: [],

        stationSignature: null,

        initializing: null,

        AdvancedMarkerElement: null,

        PinElement: null,

        latestData: null,

        activeStationId: null,

        campusMarker: null,

        campusSignature: null,

    };

    // Always store the newest data from Python.
    state.latestData = data;


    // ==================================================
    // 3. GET HTML ELEMENTS
    // ==================================================

    const mapContainer =
        parentElement.querySelector("#gsu-map");

    const slider =
        parentElement.querySelector("#gsu-radius-slider");

    const radiusLabel =
        parentElement.querySelector("#gsu-radius-value");


    // ==================================================
    // 4. RADIUS HELPERS
    // ==================================================

    function clampRadius(value) {

        const numericValue = Number(value);

        if (!Number.isFinite(numericValue)) {
            return 2.00;
        }

        return Math.min(
            MAX_RADIUS,
            Math.max(MIN_RADIUS, numericValue)
        );

    }


    function updateSliderAppearance(radius) {

        // Display radius with two decimal places.
        radiusLabel.textContent =
            radius.toFixed(2) + " miles";

        // Update the colored progress portion.
        const progress = (
            (radius - MIN_RADIUS) /
            (MAX_RADIUS - MIN_RADIUS)
        ) * 100;

        slider.style.setProperty(
            "--gsu-slider-progress",
            progress + "%"
        );

    }


    // ==================================================
    // 5. IDENTIFY VISIBLE AND CHEAPEST STATIONS
    // ==================================================

    function updateMapRadius(radius) {

        radius = clampRadius(radius);

        updateSliderAppearance(radius);

        // Map may still be loading.
        if (!state.map || !state.circle) {
            return;
        }


        // ----------------------------------------------
        // UPDATE CIRCLE
        // ----------------------------------------------

        // This modifies the existing circle instead
        // of recreating the entire Google Map.

        state.circle.setRadius(
            radius * MILES_TO_METERS
        );


        // ----------------------------------------------
        // DETERMINE VISIBLE STATIONS
        // ----------------------------------------------

        const visibleStations = state.markers.filter(
            item => item.station.distance <= radius
        );


        // ----------------------------------------------
        // IDENTIFY AND RANK ELIGIBLE STATIONS
        // ----------------------------------------------

        const PRICE_TOLERANCE = 0.000001;

        const eligibleStations = visibleStations.filter(
            item =>
                item.station.eligible &&
                Number.isFinite(item.station.price) &&
                item.station.price > 0
        );


        // Identify the minimum eligible price.
        const lowestPrice = eligibleStations.length > 0

            ? Math.min(
                ...eligibleStations.map(
                    item => item.station.price
                )
            )

            : null;


        // Identify all stations tied for the minimum.
        const cheapestStations = eligibleStations

            .filter(item =>
                lowestPrice !== null &&
                Math.abs(
                    item.station.price - lowestPrice
                ) <= PRICE_TOLERANCE
            )

            .sort((a, b) => {

                // Prefer the closest station.
                const distanceDifference =
                    a.station.distance -
                    b.station.distance;

                if (distanceDifference !== 0) {
                    return distanceDifference;
                }

                // Deterministic Place ID tie-breaker.
                return a.station.id < b.station.id
                    ? -1
                    : a.station.id > b.station.id
                        ? 1
                        : 0;

            });


        // Select one Best Value station.
        const bestStation = cheapestStations.length > 0
            ? cheapestStations[0].station
            : null;


        // ----------------------------------------------
        // UPDATE MARKER VISIBILITY AND COLORS
        // ----------------------------------------------

        for (const item of state.markers) {

            const station = item.station;

            const withinRadius =
                station.distance <= radius;

            // Show or hide marker without recreating it.
            item.marker.map = withinRadius
                ? state.map
                : null;


            // Determine whether this station is tied
            // for the lowest eligible price.
            const isCheapest = (
                withinRadius &&
                station.eligible &&
                lowestPrice !== null &&
                Number.isFinite(station.price) &&
                Math.abs(
                    station.price - lowestPrice
                ) < PRICE_TOLERANCE
            );

            const isBest = (
                isCheapest &&
                bestStation !== null &&
                station.id === bestStation.id
            );


            // Assign marker color.
            let markerColor = COLORS.unavailable;

            if (station.eligible) {
                markerColor = COLORS.eligible;
            }

            if (isCheapest) {
                markerColor = COLORS.cheapest;
            }

            if (isBest) {
                markerColor = COLORS.best;
            }

            // Update existing pin.
            item.pin.background = markerColor;

            item.pin.glyphText = isBest
                ? "★"
                : isCheapest
                    ? "$"
                    : "";

            // Make the best station more prominent.
            item.pin.scale = isBest
                ? 1.35
                : isCheapest
                    ? 1.1
                    : 1.0;

            // Prioritize the best station when markers overlap.
            item.marker.zIndex = isBest
                ? 2000
                : isCheapest
                    ? 1000
                    : 100;
        }

        // ----------------------------------------------
        // CLOSE POPUP IF ITS STATION IS HIDDEN
        // ----------------------------------------------

        if (state.activeStationId !== null) {

            const activeVisible = visibleStations.some(
                item =>
                    item.station.id ===
                    state.activeStationId
            );

            if (!activeVisible && state.infoWindow) {

                state.infoWindow.close();

                state.activeStationId = null;

            }

        }

    }


    // ==================================================
    // 6. CREATE SAFE STATION POPUP CONTENT
    // ==================================================

    
    function createStationPopup(station) {

        const container = document.createElement("div");

        container.className = "gsu-popup";


        // ----------------------------------------------
        // HELPER: CREATE POPUP ICONS
        // ----------------------------------------------

        function createIcon(type) {

            const icon = document.createElementNS(
                "http://www.w3.org/2000/svg",
                "svg"
            );

            icon.setAttribute("viewBox", "0 0 24 24");
            icon.setAttribute("fill", "none");
            icon.setAttribute("stroke", "currentColor");
            icon.setAttribute("stroke-width", "1.8");
            icon.setAttribute("stroke-linecap", "round");
            icon.setAttribute("stroke-linejoin", "round");
            icon.setAttribute("aria-hidden", "true");

            icon.classList.add("gsu-popup-icon");

            const paths = {

                location: `
                    <path d="M20 10c0 5-8 11-8 11
                             S4 15 4 10a8 8 0 1 1 16 0Z"/>
                    <circle cx="12" cy="10" r="2.5"/>
                `,

                navigation: `
                    <path d="M3 11 21 3 13 21
                             10 14 3 11Z"/>
                `,

                clock: `
                    <circle cx="12" cy="12" r="9"/>
                    <path d="M12 7v5l-3 2"/>
                `

            };

            icon.innerHTML = paths[type] || "";

            return icon;

        }


        // ----------------------------------------------
        // HELPER: CREATE AN ICON AND TEXT ROW
        // ----------------------------------------------

        function createDetailRow(type, text, className) {

            const row = document.createElement("div");

            row.className =
                "gsu-popup-row " + className;

            const label = document.createElement("span");

            label.textContent = text;

            row.appendChild(createIcon(type));

            row.appendChild(label);

            return row;

        }


        // ----------------------------------------------
        // STATION ADDRESS
        // ----------------------------------------------

        const address = (
            station.address || "Address unavailable"
        ).replace(/,\s*USA\s*$/i, "");

        container.appendChild(
            createDetailRow(
                "location",
                address,
                "gsu-popup-address"
            )
        );


        // ----------------------------------------------
        // DIVIDER
        // ----------------------------------------------

        const divider = document.createElement("hr");

        divider.className = "gsu-popup-divider";

        container.appendChild(divider);


        // ----------------------------------------------
        // REGULAR GAS PRICE
        // ----------------------------------------------

        const priceLine = document.createElement("div");

        priceLine.className = "gsu-popup-price-line";

        const priceValue = document.createElement("span");

        priceValue.className = "gsu-popup-price";

        if (
            Number.isFinite(station.price) &&
            station.price > 0
        ) {

            priceValue.textContent =
                "$" + station.price.toFixed(2);

            const priceUnit = document.createElement("span");

            priceUnit.className = "gsu-popup-unit";

            priceUnit.textContent = "per gallon";

            priceLine.appendChild(priceValue);

            priceLine.appendChild(priceUnit);

        } else {

            priceValue.textContent = "Price unavailable";

            priceValue.classList.add(
                "gsu-popup-price-unavailable"
            );

            priceLine.appendChild(priceValue);

        }

        container.appendChild(priceLine);


        // ----------------------------------------------
        // PRICE ELIGIBILITY WARNING
        // ----------------------------------------------

        if (
            Number.isFinite(station.price) &&
            station.price > 0 &&
            !station.eligible
        ) {

            const warning = document.createElement("div");

            warning.className = "gsu-popup-warning";

            warning.textContent =
                "Price does not meet freshness requirements.";

            container.appendChild(warning);

        }


        // ----------------------------------------------
        // DISTANCE FROM CAMPUS
        // ----------------------------------------------

        container.appendChild(
            createDetailRow(

                "navigation",

                station.distance.toFixed(2) +
                " miles from campus",

                "gsu-popup-distance"

            )
        );


        // ----------------------------------------------
        // PRICE AGE
        // ----------------------------------------------

        const ageText = Number.isFinite(station.age)

            ? "Price age: " +
              station.age.toFixed(1) +
              " hours"

            : "Price update time unavailable";

        container.appendChild(
            createDetailRow(
                "clock",
                ageText,
                "gsu-popup-age"
            )
        );


        return container;

    }


    // ==================================================
    // 7. SYNCHRONIZE GAS STATION MARKERS
    // ==================================================

    function syncStationMarkers() {

        if (!state.map) {
            return;
        }

        const stations =
            state.latestData.stations || [];

        // Identify whether the actual station data changed.
        const signature = JSON.stringify(stations);


        if (signature !== state.stationSignature) {

            // ------------------------------------------
            // REMOVE PREVIOUS STATION MARKERS
            // ------------------------------------------

            for (const item of state.markers) {

                item.marker.map = null;

            }

            state.markers = [];

            if (state.infoWindow) {
                state.infoWindow.close();
            }

            state.activeStationId = null;


            // ------------------------------------------
            // CREATE NEW STATION MARKERS
            // ------------------------------------------

            for (const station of stations) {

                // Create colored station pin.
                const pin = new state.PinElement({

                    background: station.eligible
                        ? COLORS.eligible
                        : COLORS.unavailable,

                    borderColor: "#ffffff",

                    glyphColor: "#ffffff",

                    scale: 1

                });


                // Create marker.
                const marker =
                    new state.AdvancedMarkerElement({

                        map: state.map,

                        position: {
                            lat: station.lat,
                            lng: station.lng
                        },

                        title: station.name,

                        content: pin,

                        gmpClickable: true,

                        zIndex: 100

                    });


                // --------------------------------------
                // HANDLE MARKER CLICKS
                // --------------------------------------

                marker.addEventListener(
                    "gmp-click",
                    () => {

                        if (state.infoWindow) {

                            state.infoWindow.close();

                        }

                        const popup = createStationPopup(station);


                        // Create the station name in the popup header.
                        const heading = document.createElement("div");

                        heading.className = "gsu-popup-heading";

                        heading.textContent = station.name;

                        state.infoWindow.setHeaderContent(heading);


                        // Set the popup body.
                        state.infoWindow.setContent(popup);


                        // Open the popup.
                        state.infoWindow.open({

                            map: state.map,

                            anchor: marker

                        });

                        state.activeStationId =
                            station.id;

                    }
                );


                state.markers.push({

                    station: station,

                    marker: marker,

                    pin: pin

                });

            }


            // Remember which dataset is displayed.
            state.stationSignature = signature;

        }


        // Apply current radius after data changes.
        updateMapRadius(
            Number(slider.value)
        );

    }


    // ==================================================
    // 8. SLIDER INTERACTIONS
    // ==================================================

    // Set the slider to the radius supplied by Python.
    const initialRadius = clampRadius(
        data.radius ?? 2.00
    );

    slider.value = initialRadius.toFixed(2);

    updateSliderAppearance(initialRadius);


    // ----------------------------------------------
    // LIVE UPDATES WHILE DRAGGING
    // ----------------------------------------------

    slider.oninput = () => {

        const newRadius = clampRadius(
            slider.value
        );

        updateMapRadius(newRadius);

    };


    // ----------------------------------------------
    // SYNCHRONIZE WITH STREAMLIT ON RELEASE
    // ----------------------------------------------

    slider.onchange = () => {

        const selectedRadius = clampRadius(
            slider.value
        );

        // Update Python state only when the user
        // commits the selected radius.
        setStateValue(
            "radius",
            selectedRadius
        );

    };


    // ==================================================
    // 9. LOAD GOOGLE MAPS JAVASCRIPT API
    // ==================================================

    async function loadGoogleMaps(apiKey) {

        // Google Maps may already be available.
        if (window.google?.maps?.importLibrary) {
            return;
        }


        // Share the loading promise across reruns.
        if (!window._gsuGoogleMapsPromise) {

            window._gsuGoogleMapsPromise = new Promise(
                (resolve, reject) => {

                    const callbackName =
                        "__gsuGoogleMapsReady";

                    window[callbackName] = () => {

                        delete window[callbackName];

                        resolve();

                    };


                    const script =
                        document.createElement("script");

                    script.src =
                        "https://maps.googleapis.com/maps/api/js" +
                        "?key=" +
                        encodeURIComponent(apiKey) +
                        "&loading=async" +
                        "&callback=" +
                        callbackName +
                        "&v=weekly";

                    script.async = true;


                    script.onerror = () => {

                        delete window[callbackName];

                        reject(
                            new Error(
                                "Google Maps JavaScript API " +
                                "failed to load."
                            )
                        );

                    };


                    document.head.appendChild(script);

                }
            ).catch(error => {

                window._gsuGoogleMapsPromise = null;

                throw error;

            });

        }


        await window._gsuGoogleMapsPromise;

    }

    // ==================================================
    // SYNCHRONIZE CAMPUS LOCATION
    // ==================================================

    function syncCampusLocation() {

        if (!state.map || !state.campusMarker) {
            return;
        }

        // Retrieve the selected campus
        const campus = state.latestData.campus;

        // Create an identifier for the campus
        const signature = JSON.stringify(campus);

        // Do nothing if the campus has not changed
        if (signature === state.campusSignature) {
            return;
        }

        // Extract campus coordinates
        const position = {
            lat: campus.lat,
            lng: campus.lng
        };

        // Close any previous station popup
        if (state.infoWindow) {
            state.infoWindow.close();
        }

        state.activeStationId = null;

        // Move the campus marker
        state.campusMarker.position = position;

        // Update the marker title
        state.campusMarker.title =
            `GSU ${campus.name} Campus`;

        // Move the search radius circle
        state.circle.setCenter(position);

        // Create bounds for the new campus search area
        const maximumCircle = new google.maps.Circle({
            center: position,
            radius: MAX_RADIUS * MILES_TO_METERS
        });

        const bounds = maximumCircle.getBounds();

        // Recenter and fit the map
        if (bounds) {
            state.map.fitBounds(bounds);
        } else {
            state.map.setCenter(position);
        }

        // Record the newly displayed campus
        state.campusSignature = signature;
    }


    // ==================================================
    // 10. INITIALIZE GOOGLE MAP
    // ==================================================

    async function initializeMap() {

        const currentData = state.latestData;

        // Use browser-restricted API key.
        await loadGoogleMaps(
            currentData.apiKey
        );


        // Load required Google Maps libraries.
        const { Map, Circle, InfoWindow } =
            await google.maps.importLibrary("maps");

        const {
            AdvancedMarkerElement,
            PinElement
        } = await google.maps.importLibrary("marker");


        state.AdvancedMarkerElement =
            AdvancedMarkerElement;

        state.PinElement =
            PinElement;


        // ----------------------------------------------
        // CREATE MAP ONCE
        // ----------------------------------------------

        if (!state.map) {

            const campus =
                state.latestData.campus;


            state.map = new Map(

                mapContainer,

                {
                    center: campus,

                    zoom: 12,

                    mapId: "DEMO_MAP_ID",

                    mapTypeControl: false,

                    fullscreenControl: true
                }

            );


            // ------------------------------------------
            // CREATE RADIUS CIRCLE ONCE
            // ------------------------------------------

            state.circle = new Circle({

                map: state.map,

                center: campus,

                radius:
                    Number(slider.value) *
                    MILES_TO_METERS,

                strokeColor: COLORS.radius,

                strokeOpacity: 0.8,

                strokeWeight: 2,

                fillColor: COLORS.radius,

                fillOpacity: 0.08

            });


            // ------------------------------------------
            // CREATE SHARED INFO WINDOW
            // ------------------------------------------

            state.infoWindow =
                new InfoWindow({
                    maxWidth: 320
                });


            // ------------------------------------------
            // CREATE GSU CAMPUS MARKER
            // ------------------------------------------

            const campusPin = new PinElement({

                background: COLORS.campus,

                borderColor: "#92400e",

                glyphColor: "#ffffff",

                glyphText: "G",

                scale: 1.3

            });


            state.campusMarker = new AdvancedMarkerElement({
                map: state.map,

                position: {
                    lat: campus.lat,
                    lng: campus.lng
                },

                content: campusPin,

                title: `GSU ${campus.name} Campus`,

                zIndex: 2000
            });

            state.campusSignature = JSON.stringify(campus);


            // ------------------------------------------
            // SET INITIAL MAP VIEW
            // ------------------------------------------

            // Fit the maximum search area once.
            // After this, moving the slider will not
            // repeatedly reset the map's zoom level.

            const maximumCircle = new Circle({

                center: campus,

                radius:
                    MAX_RADIUS * MILES_TO_METERS

            });

            const bounds =
                maximumCircle.getBounds();

            if (bounds) {

                state.map.fitBounds(bounds);

            }

        }


        // Add stations and apply the selected radius.
        syncCampusLocation();
        syncStationMarkers();

    }


    // ==================================================
    // 11. UPDATE EXISTING MAP OR INITIALIZE NEW ONE
    // ==================================================

    if (state.map) {

        // Update campus location if necessary
        syncCampusLocation();

        // Update gas station markers
        syncStationMarkers();

    } else if (!state.initializing) {

        // Initialize only once per mounted component.
        state.initializing = initializeMap()
            .catch(error => {

                console.error(
                    "GSU Google Maps error:",
                    error
                );

                state.initializing = null;

                mapContainer.textContent =
                    "Unable to load Google Maps. " +
                    "Check the browser console " +
                    "and API configuration.";

            });

    }

}
