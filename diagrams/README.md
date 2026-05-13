# Technical Documentation Diagrams

This directory contains Mermaid diagram files referenced in the technical documentation.

## Diagram Files

### 1. System Integration Flow
**File**: `system-integration-flow.mmd`  
**Type**: Flowchart  
**Description**: High-level overview of the complete integration flow from Odoo POS transaction creation through NetSuite processing, including real-time, scheduled, and manual sync paths.

### 2. Consolidated Invoice Flow
**File**: `consolidated-invoice-flow.mmd`  
**Type**: Flowchart  
**Description**: Visualization of the consolidation logic showing how multiple orders are aggregated into a single NetSuite invoice with combined line items.

### 3. End of Day Sequence
**File**: `end-of-day-sequence.mmd`  
**Type**: Sequence Diagram  
**Description**: Detailed sequence diagram of the midnight end-of-day sync process, showing interactions between Odoo components and NetSuite.

## Viewing Diagrams

### In VS Code
1. Install the Mermaid Preview extension
2. Open any `.mmd` file
3. Use the preview pane to view the rendered diagram

### Online
1. Visit [Mermaid Live Editor](https://mermaid.live/)
2. Copy the contents of any `.mmd` file
3. Paste into the editor to view and edit

### In Documentation
These diagrams are embedded in the `TECHNICAL_DOCUMENTATION.md` file using Mermaid code blocks.

## Editing Diagrams

To modify any diagram:
1. Edit the corresponding `.mmd` file
2. Update the matching Mermaid code block in `TECHNICAL_DOCUMENTATION.md`
3. Regenerate the .docx file using:
   ```bash
   pandoc TECHNICAL_DOCUMENTATION.md -o "Odoo_NetSuite_Integration_Technical_Documentation.docx" --toc --toc-depth=3 --number-sections
   ```

## Diagram Standards

All diagrams follow these conventions:
- **Odoo components**: Light blue fill (`#e1f5ff`)
- **NetSuite components**: Light yellow fill (`#fff4e1`)
- **Processing/Service components**: Light green fill (`#d4edda`)
- **Error states**: Light red fill (`#f8d7da`)
- **Queue/Async operations**: Light yellow fill (`#fff3cd`)
