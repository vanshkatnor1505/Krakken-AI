
import QtQuick
import QtQuick.Layouts

import Kraken

Rectangle {

    id: root

    // ----------------------------------------------------------
    // Base
    // ----------------------------------------------------------

    implicitHeight: Theme.statusBarHeight

    color: Theme.surface

    border.color: Theme.border
    border.width: 1

    // ----------------------------------------------------------
    // Status data
    //
    // These are placeholders for now.
    // Later they will be connected to the Python backend.
    // ----------------------------------------------------------

    readonly property var statusItems: [
        {
            label: "CPU",
            value: "0%",
            state: "normal"
        },
        {
            label: "RAM",
            value: "0%",
            state: "normal"
        },
        {
            label: "VOICE",
            value: "READY",
            state: "success"
        },
        {
            label: "AI",
            value: "ONLINE",
            state: "success"
        },
        {
            label: "MEMORY",
            value: "READY",
            state: "success"
        }
    ]

    // ----------------------------------------------------------
    // Status layout
    // ----------------------------------------------------------

    RowLayout {

        anchors.fill: parent

        anchors.leftMargin: Theme.spacingXL
        anchors.rightMargin: Theme.spacingXL

        spacing: Theme.spacingXXL

        Repeater {

            model: root.statusItems

            delegate: RowLayout {

                spacing: Theme.spacingS

                // ----------------------------------------------
                // Status indicator
                // ----------------------------------------------

                Rectangle {

                    Layout.alignment: Qt.AlignVCenter

                    width: 7
                    height: 7

                    radius: 3.5

                    color: {

                        switch (modelData.state) {

                        case "success":
                            return Theme.accentGreen

                        case "warning":
                            return Theme.warning

                        case "danger":
                            return Theme.danger

                        default:
                            return Theme.accent
                        }
                    }

                    SequentialAnimation on opacity {

                        loops: Animation.Infinite

                        NumberAnimation {

                            from: 1.0
                            to: 0.45

                            duration: 1200
                        }

                        NumberAnimation {

                            from: 0.45
                            to: 1.0

                            duration: 1200
                        }
                    }
                }

                // ----------------------------------------------
                // Label
                // ----------------------------------------------

                Text {

                    text: modelData.label

                    color: Theme.textSecondary

                    font.pixelSize: Theme.fontSmall

                    font.bold: true

                    Layout.alignment: Qt.AlignVCenter
                }

                // ----------------------------------------------
                // Value
                // ----------------------------------------------

                Text {

                    text: modelData.value

                    color: {

                        switch (modelData.state) {

                        case "success":
                            return Theme.accentGreen

                        case "warning":
                            return Theme.warning

                        case "danger":
                            return Theme.danger

                        default:
                            return Theme.textPrimary
                        }
                    }

                    font.pixelSize: Theme.fontSmall

                    font.bold: true

                    Layout.alignment: Qt.AlignVCenter
                }
            }
        }

        Item {
            Layout.fillWidth: true
        }

        // ------------------------------------------------------
        // Kraken status
        // ------------------------------------------------------

        RowLayout {

            spacing: Theme.spacingS

            Rectangle {

                width: 7
                height: 7

                radius: 3.5

                color: Theme.accentGreen
            }

            Text {

                text: "KRAKKEN CORE"

                color: Theme.textSecondary

                font.pixelSize: Theme.fontSmall

                font.bold: true
            }
        }
    }
}

