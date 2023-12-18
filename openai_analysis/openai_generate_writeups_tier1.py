import json
import os
import re
import openai

# Add the taxonomy_tier1 list
taxonomy_tier1_list = [
    "Web Interaction and Navigation",
    "Authentication, Session, and User Management",
    "Data Analysis, Manipulation, and Storage Interactions",
    "Code, Application, and Script Analysis",
    "Exploitation Techniques and Payload Handling",
    "Network and System Analysis",
    "Debugging, Monitoring, and Troubleshooting",
    "Cryptography, Encoding, and Decoding Techniques",
    "Tools, Scripting, and System Interactions",
    "Information Gathering and Security Analysis",
    "Documentation, Strategy, and Miscellaneous Techniques",
    "N/A",
]


def get_response(messages: list):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
        stream=False,
    )
    return response.choices[0].message.content


def find_substeps_files_without_tier1():
    substeps_filepaths = []
    for dirpath, _, filenames in os.walk("../dataset_writeups"):
        for filename in filenames:
            if (
                "_substeps_" in filename
                and filename.endswith(".json")
                and not filename.endswith("_tier1.json")
            ):
                substeps_filepath = os.path.join(dirpath, filename)
                tier1_filepath = substeps_filepath.replace(".json", "_tier1.json")
                if not os.path.exists(tier1_filepath):
                    substeps_filepaths.append(substeps_filepath)
    return substeps_filepaths


def extract_json(s: str):
    for match in re.finditer(r"{[^}]*}", s):
        substr = s[match.start() :]
        for end in range(len(substr), 0, -1):
            try:
                potential_json = json.loads(substr[:end])
                return potential_json
            except json.JSONDecodeError:
                continue
    return None


if __name__ == "__main__":
    with open("./api_keys.json", "r", encoding="utf-8") as f:
        api_key = json.load(f)["api_key"]
    openai.api_key = api_key
    with open(
        "./prompts/prompt_tier1taxonomy_labelling_minimal.txt", "r", encoding="utf-8"
    ) as f:
        taxonomy_requirements = f.read()

    try:
        substeps_filepaths = find_substeps_files_without_tier1()
        total_files = len(substeps_filepaths)

        for idx, subteps_filepath in enumerate(substeps_filepaths, start=1):
            with open(subteps_filepath, "r", encoding="utf-8") as substeps_file:
                substeps = substeps_file.read()
            messages = [
                {
                    "role": "user",
                    "content": taxonomy_requirements + substeps,
                }
            ]

            print(f"[{idx}/{total_files}] Processing `{subteps_filepath}`")
            try:
                response = get_response(messages=messages)
            except openai.error.InvalidRequestError as e:
                print(f"ERROR - OpenAI - {e}")

            response_json_data = extract_json(response)

            if response_json_data is not None:
                if all(
                    key in response_json_data
                    for key in ["StepNumber", "StepString", "Substeps"]
                ):
                    all_substeps_valid = True

                    for substep in response_json_data.get("Substeps", []):
                        all_fields_present = all(
                            key in substep
                            for key in [
                                "SubstepNumber",
                                "SubstepString",
                                "Tier1TaxonomyMain",
                                "Tier1TaxonomyAlternative",
                            ]
                        )

                        if not all_fields_present:
                            print(
                                f"ERROR - Substep {substep.get('SubstepNumber', 'Unknown')} is missing some fields."
                            )
                            all_substeps_valid = False
                            break

                        taxonomy_values_valid = (
                            substep.get("Tier1TaxonomyMain") in taxonomy_tier1_list
                        ) and (
                            substep.get("Tier1TaxonomyAlternative")
                            in taxonomy_tier1_list
                        )

                        if not substep.get("Tier1TaxonomyMain") or not substep.get(
                            "Tier1TaxonomyAlternative"
                        ):
                            print(
                                f"ERROR - Substep {substep.get('SubstepNumber', 'Unknown')} is missing taxonomy fields."
                            )
                            all_substeps_valid = False
                            break

                        if not taxonomy_values_valid:
                            print(
                                f"ERROR - Substep {substep.get('SubstepNumber', 'Unknown')} has invalid taxonomy values. Main: {substep.get('Tier1TaxonomyMain')}, Alternative: {substep.get('Tier1TaxonomyAlternative')}."
                            )
                            all_substeps_valid = False
                            break

                        if substep.get("Tier1TaxonomyMain") == substep.get(
                            "Tier1TaxonomyAlternative"
                        ):
                            print(
                                f"ERROR - Substep {substep.get('SubstepNumber', 'Unknown')} has identical values for Tier1TaxonomyMain and Tier1TaxonomyAlternative."
                            )
                            all_substeps_valid = False
                            break

                    if all_substeps_valid:
                        print("INFO - JSON appears to be well-formed and complete.")
                        tier1_filepath = subteps_filepath.replace(
                            ".json", "_tier1.json"
                        )
                        with open(tier1_filepath, "w", encoding="utf-8") as tier1_file:
                            json.dump(response_json_data, tier1_file, indent=4)
                        print(f"Saved `{tier1_filepath}`")
                else:
                    print("ERROR - JSON is missing expected keys or values.")
            else:
                print("ERROR - JSON may be truncated or invalid.")

    except KeyboardInterrupt:
        print("Stop.")
