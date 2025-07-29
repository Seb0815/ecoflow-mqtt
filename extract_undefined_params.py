#!/usr/bin/env python3
"""
Extrahiert undefinierte Parameter aus den EcoFlow MQTT Log-Ausgaben
"""

import re
import sys
import json
from collections import defaultdict

def extract_undefined_params_from_log(log_content):
    """Extrahiert alle undefinierten Parameter aus Log-Inhalten"""
    
    # Pattern für UNDEFINED PARAMETERS Zeilen
    undefined_pattern = r'UNDEFINED PARAMETERS for (\w+) \((\w+)\): (\d+) parameters found'
    params_pattern = r'UNDEFINED PARAMETERS: (.+?)(?:\n|$)'
    interesting_pattern = r'INTERESTING UNDEFINED for (\w+): ({.+?})'
    
    results = defaultdict(lambda: {
        'device_type': None,
        'device_sn': None,
        'total_count': 0,
        'parameters': set(),
        'interesting_parameters': {}
    })
    
    lines = log_content.split('\n')
    
    for i, line in enumerate(lines):
        # Suche nach UNDEFINED PARAMETERS Header
        match = re.search(undefined_pattern, line)
        if match:
            device_type = match.group(1)
            device_sn = match.group(2)
            param_count = int(match.group(3))
            
            key = f"{device_type}_{device_sn}"
            results[key]['device_type'] = device_type
            results[key]['device_sn'] = device_sn
            results[key]['total_count'] = max(results[key]['total_count'], param_count)
            
            # Schaue in der nächsten Zeile nach den Parameter-Details
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                params_match = re.search(params_pattern, next_line)
                if params_match:
                    params_str = params_match.group(1)
                    
                    # Extrahiere Parameter-Namen (vor dem = Zeichen)
                    param_names = []
                    for param in params_str.split(', '):
                        if '=' in param:
                            param_name = param.split('=')[0].strip()
                            param_names.append(param_name)
                        elif param.endswith('>'):
                            # Format: param_name=<type>
                            param_name = param.split('=')[0].strip()
                            param_names.append(param_name)
                    
                    results[key]['parameters'].update(param_names)
        
        # Suche nach INTERESTING UNDEFINED
        interesting_match = re.search(interesting_pattern, line)
        if interesting_match:
            device_type = interesting_match.group(1)
            params_dict_str = interesting_match.group(2)
            
            try:
                # Konvertiere zu Python dict
                params_dict = eval(params_dict_str)  # Vorsicht: nur für vertrauenswürdige Logs!
                
                # Finde den entsprechenden Key
                for key in results:
                    if results[key]['device_type'] == device_type:
                        results[key]['interesting_parameters'].update(params_dict)
                        break
            except:
                pass  # Ignore parsing errors
    
    return dict(results)

def format_results(results):
    """Formatiert die Ergebnisse für die Ausgabe"""
    
    if not results:
        print("Keine undefinierten Parameter gefunden.")
        return
    
    print("=" * 80)
    print("UNDEFINED PARAMETER EXTRACTION RESULTS")
    print("=" * 80)
    
    # Gruppiere nach Device-Typ
    by_device_type = defaultdict(list)
    for key, data in results.items():
        by_device_type[data['device_type']].append(data)
    
    for device_type, devices in by_device_type.items():
        print(f"\n🔹 {device_type}")
        print("-" * 60)
        
        # Sammle alle Parameter für diesen Device-Typ
        all_params = set()
        all_interesting = {}
        
        for device in devices:
            all_params.update(device['parameters'])
            all_interesting.update(device['interesting_parameters'])
            print(f"  Device: {device['device_sn']} ({device['total_count']} undefined params)")
        
        if all_params:
            print(f"  All undefined parameters ({len(all_params)}):")
            sorted_params = sorted(list(all_params))
            for i in range(0, len(sorted_params), 4):
                batch = sorted_params[i:i+4]
                print(f"    {', '.join(batch)}")
        
        if all_interesting:
            print(f"  Interesting parameters with values:")
            for param, value in sorted(all_interesting.items()):
                print(f"    {param} = {value}")
        
        # Generiere Code-Template für device_param_map
        if all_params:
            print(f"\n  Code template for {device_type}:")
            print(f'    "{device_type}": {{')
            sorted_params = sorted(list(all_params))
            for i in range(0, len(sorted_params), 5):
                batch = sorted_params[i:i+5]
                batch_str = ', '.join(f'"{p}"' for p in batch)
                print(f'        {batch_str},')
            print(f'    }},')

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_undefined_params.py <log_file>")
        print("       oder")
        print("       docker logs <container> | python3 extract_undefined_params.py -")
        print("       oder")
        print("       journalctl -u <service> | python3 extract_undefined_params.py -")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        if log_file == '-':
            # Lese von stdin
            log_content = sys.stdin.read()
        else:
            # Lese von Datei
            with open(log_file, 'r', encoding='utf-8') as f:
                log_content = f.read()
        
        results = extract_undefined_params_from_log(log_content)
        format_results(results)
        
        # Optional: Speichere als JSON
        if results:
            output_file = 'undefined_parameters.json'
            # Konvertiere sets zu lists für JSON
            json_results = {}
            for key, data in results.items():
                json_results[key] = {
                    'device_type': data['device_type'],
                    'device_sn': data['device_sn'],
                    'total_count': data['total_count'],
                    'parameters': sorted(list(data['parameters'])),
                    'interesting_parameters': data['interesting_parameters']
                }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(json_results, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 Detailed results saved to: {output_file}")
        
    except FileNotFoundError:
        print(f"Error: Log file '{log_file}' not found.")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing log: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
